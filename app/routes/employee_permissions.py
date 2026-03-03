"""
Employee Permission Overrides API
==================================
Allows branch admins to grant or revoke individual permissions from an
employee beyond what their role defines.

Endpoints
---------
GET    /employee-permissions/{employee_id}          – get effective perms (resolved)
GET    /employee-permissions/{employee_id}/override  – get raw override doc
POST   /employee-permissions/{employee_id}/override  – create override
PUT    /employee-permissions/{employee_id}/override  – update override
DELETE /employee-permissions/{employee_id}/override  – remove override (revert to role)
GET    /employee-permissions/{employee_id}/check     – check single permission
"""
from datetime import datetime
from typing import Optional, List

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config.database import db_config
from app.rbac.models import (
    EmployeePermissionOverrideCreate,
    EmployeePermissionOverrideUpdate,
)
from app.rbac.permissions import ALL_PERMISSION_CODES
from app.rbac.service import resolve_permissions, has_permission, _is_super_admin
from app.utils.auth import get_current_user
from app.utils.helpers import serialize_doc

router = APIRouter(prefix="/employee-permissions", tags=["Employee Permissions (RBAC)"])

_COL_OVR = "employee_permission_overrides"
_COL_EMP = "employees"


def _col():
    return db_config.get_collection(_COL_OVR)


def _now():
    return datetime.utcnow()


def _validate_codes(codes: List[str]) -> List[str]:
    invalid = [c for c in codes if c not in ALL_PERMISSION_CODES]
    if invalid:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Invalid permission codes: {invalid}",
        )
    return codes


def _assert_branch_access(current_user: dict, branch_id: str):
    """Ensure caller can manage permissions in this branch."""
    if _is_super_admin(current_user):
        return
    token_branch = current_user.get("branch_id") or current_user.get("entity_id") or ""
    if str(token_branch) != str(branch_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You can only manage permissions within your own branch",
        )


# ─── GET effective permissions (resolved) ─────────────────────────────────────

@router.get(
    "/{employee_id}/effective",
    summary="Get fully-resolved effective permission set for an employee",
)
async def get_effective_permissions(
    employee_id: str,
    branch_id: str = Query(...),
    organization_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    org_id = organization_id or current_user.get("organization_id") or ""
    _assert_branch_access(current_user, branch_id)

    effective, source = await resolve_permissions(employee_id, branch_id, org_id)
    return {
        "employee_id": employee_id,
        "branch_id": branch_id,
        "source": source,
        "permission_count": len(effective),
        "permissions": sorted(effective),
    }


# ─── GET raw override doc ──────────────────────────────────────────────────────

@router.get(
    "/{employee_id}/override",
    summary="Get raw permission override for an employee (if any)",
)
async def get_override(
    employee_id: str,
    branch_id: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    _assert_branch_access(current_user, branch_id)
    doc = await _col().find_one({"employee_id": employee_id, "branch_id": branch_id})
    if not doc:
        return {"message": "No custom override set for this employee", "employee_id": employee_id}
    return serialize_doc(doc)


# ─── CREATE override ──────────────────────────────────────────────────────────

@router.post(
    "/{employee_id}/override",
    summary="Create a permission override for an employee",
    status_code=status.HTTP_201_CREATED,
)
async def create_override(
    employee_id: str,
    body: EmployeePermissionOverrideCreate,
    current_user: dict = Depends(get_current_user),
):
    _assert_branch_access(current_user, body.branch_id)

    # Validate codes
    granted = _validate_codes(body.granted)
    revoked = _validate_codes(body.revoked)

    # Ensure revoked ∩ granted = ∅
    conflict = set(granted) & set(revoked)
    if conflict:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Codes cannot be both granted and revoked: {sorted(conflict)}",
        )

    col = _col()
    existing = await col.find_one({"employee_id": employee_id, "branch_id": body.branch_id})
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Override already exists. Use PUT to update it.",
        )

    doc = body.model_dump()
    doc["employee_id"] = employee_id
    doc["granted"] = granted
    doc["revoked"] = revoked
    doc["created_at"] = _now()
    doc["updated_at"] = _now()

    result = await col.insert_one(doc)
    created = await col.find_one({"_id": result.inserted_id})
    return serialize_doc(created)


# ─── UPDATE override ──────────────────────────────────────────────────────────

@router.put(
    "/{employee_id}/override",
    summary="Update (upsert) a permission override for an employee",
)
async def update_override(
    employee_id: str,
    body: EmployeePermissionOverrideUpdate,
    branch_id: str = Query(...),
    organization_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    _assert_branch_access(current_user, branch_id)

    col = _col()
    existing = await col.find_one({"employee_id": employee_id, "branch_id": branch_id})

    update: dict = {"updated_at": _now()}

    if body.granted is not None:
        update["granted"] = _validate_codes(body.granted)
    if body.revoked is not None:
        update["revoked"] = _validate_codes(body.revoked)
    if body.note is not None:
        update["note"] = body.note

    # Validate no code is in both granted and revoked after merge
    final_granted = set(update.get("granted", existing.get("granted", []) if existing else []))
    final_revoked = set(update.get("revoked", existing.get("revoked", []) if existing else []))
    conflict = final_granted & final_revoked
    if conflict:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Codes cannot be both granted and revoked: {sorted(conflict)}",
        )

    if existing:
        await col.update_one({"_id": existing["_id"]}, {"$set": update})
        doc = await col.find_one({"_id": existing["_id"]})
    else:
        # upsert
        org_id = organization_id or current_user.get("organization_id") or ""
        new_doc = {
            "employee_id": employee_id,
            "branch_id": branch_id,
            "organization_id": org_id,
            "granted": list(final_granted),
            "revoked": list(final_revoked),
            "note": body.note,
            "created_at": _now(),
            **update,
        }
        result = await col.insert_one(new_doc)
        doc = await col.find_one({"_id": result.inserted_id})

    return serialize_doc(doc)


# ─── DELETE override ──────────────────────────────────────────────────────────

@router.delete(
    "/{employee_id}/override",
    summary="Remove custom override – employee reverts to pure role permissions",
)
async def delete_override(
    employee_id: str,
    branch_id: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    _assert_branch_access(current_user, branch_id)
    col = _col()
    existing = await col.find_one({"employee_id": employee_id, "branch_id": branch_id})
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No override found for this employee")
    await col.delete_one({"_id": existing["_id"]})
    return {"message": "Override removed. Employee now inherits role permissions only."}


# ─── CHECK single permission ──────────────────────────────────────────────────

@router.get(
    "/{employee_id}/check",
    summary="Check whether an employee has a specific permission",
)
async def check_permission(
    employee_id: str,
    permission: str = Query(..., description="e.g. bookings.ticket.view"),
    branch_id: str = Query(...),
    organization_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    org_id = organization_id or current_user.get("organization_id") or ""
    effective, source = await resolve_permissions(employee_id, branch_id, org_id)
    granted = permission in effective
    return {
        "employee_id": employee_id,
        "branch_id": branch_id,
        "permission": permission,
        "granted": granted,
        "source": source,
    }
