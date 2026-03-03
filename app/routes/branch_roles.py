"""
Branch Roles API
================
CRUD for role definitions that live at org or branch scope.

Endpoints
---------
GET    /branch-roles/catalogue               – full permission catalogue
GET    /branch-roles/predefined-templates    – seeded role templates
POST   /branch-roles/seed/{org_id}           – seed predefined roles for org
GET    /branch-roles/                        – list roles (filter by org/branch)
POST   /branch-roles/                        – create custom role
GET    /branch-roles/{role_id}               – get single role
PUT    /branch-roles/{role_id}               – update role
DELETE /branch-roles/{role_id}               – delete custom role (predefined → 403)
"""
from datetime import datetime
from typing import Optional, List

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config.database import db_config
from app.rbac.models import BranchRoleCreate, BranchRoleUpdate
from app.rbac.permissions import (
    ALL_PERMISSION_CODES,
    PERMISSION_CATALOGUE,
    PREDEFINED_ROLES,
)
from app.rbac.service import seed_predefined_roles, _is_super_admin
from app.utils.auth import get_current_user
from app.utils.helpers import serialize_doc, serialize_docs

router = APIRouter(prefix="/branch-roles", tags=["Branch Roles (RBAC)"])

_COL = "branch_roles"


def _col():
    return db_config.get_collection(_COL)


def _now():
    return datetime.utcnow()


# ─── helpers ─────────────────────────────────────────────────────────────────

def _validate_codes(codes: List[str]) -> List[str]:
    invalid = [c for c in codes if c not in ALL_PERMISSION_CODES]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid permission codes: {invalid}",
        )
    return codes


# ─── catalogue / templates ───────────────────────────────────────────────────

@router.get("/catalogue", summary="Full permission catalogue grouped by module")
async def get_catalogue():
    """Returns every module/submodule/permission for frontend checkbox rendering."""
    return PERMISSION_CATALOGUE


@router.get("/predefined-templates", summary="Predefined role templates with default permissions")
async def get_predefined_templates():
    return [
        {"key": k, "permissions": v}
        for k, v in PREDEFINED_ROLES.items()
    ]


# ─── seed ─────────────────────────────────────────────────────────────────────

@router.post(
    "/seed/{org_id}",
    summary="Seed predefined roles for an organisation (optionally scoped to a branch)",
    status_code=status.HTTP_201_CREATED,
)
async def seed_roles(
    org_id: str,
    branch_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    if not _is_super_admin(current_user):
        # only org-level admins or super admins can seed
        token_org = current_user.get("organization_id", "")
        if str(token_org) != org_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized for this organization")

    await seed_predefined_roles(org_id, branch_id)
    return {"message": "Predefined roles seeded successfully"}


# ─── LIST ─────────────────────────────────────────────────────────────────────

@router.get("/", summary="List roles for an org / branch")
async def list_roles(
    organization_id: Optional[str] = Query(None),
    branch_id: Optional[str] = Query(None),
    include_org_wide: bool = Query(True, description="Also include org-wide (branch_id=null) roles"),
    current_user: dict = Depends(get_current_user),
):
    col = _col()
    query: dict = {}

    # Resolve org_id from token if not provided
    org_id = organization_id or current_user.get("organization_id") or ""
    if org_id:
        query["organization_id"] = org_id

    if branch_id:
        if include_org_wide:
            query["$or"] = [{"branch_id": branch_id}, {"branch_id": None}]
        else:
            query["branch_id"] = branch_id

    docs = await col.find(query).sort("name", 1).to_list(length=500)
    return serialize_docs(docs)


# ─── CREATE ───────────────────────────────────────────────────────────────────

@router.post("/", summary="Create a custom role", status_code=status.HTTP_201_CREATED)
async def create_role(
    body: BranchRoleCreate,
    current_user: dict = Depends(get_current_user),
):
    # Validate permission codes
    valid_perms = _validate_codes(body.permissions)

    col = _col()
    # Prevent duplicate name within same scope
    dup = await col.find_one({
        "organization_id": body.organization_id,
        "branch_id": body.branch_id,
        "name": body.name,
    })
    if dup:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Role '{body.name}' already exists in this scope",
        )

    doc = body.model_dump()
    doc["permissions"] = valid_perms
    doc["is_predefined"] = False   # API-created roles are never predefined
    doc["created_at"] = _now()
    doc["updated_at"] = _now()
    result = await col.insert_one(doc)
    created = await col.find_one({"_id": result.inserted_id})
    return serialize_doc(created)


# ─── GET ONE ──────────────────────────────────────────────────────────────────

@router.get("/{role_id}", summary="Get a single role")
async def get_role(role_id: str, current_user: dict = Depends(get_current_user)):
    col = _col()
    doc = await col.find_one({"_id": ObjectId(role_id)}) if ObjectId.is_valid(role_id) else None
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    return serialize_doc(doc)


# ─── UPDATE ───────────────────────────────────────────────────────────────────

@router.put("/{role_id}", summary="Update a role")
async def update_role(
    role_id: str,
    body: BranchRoleUpdate,
    current_user: dict = Depends(get_current_user),
):
    col = _col()
    doc = await col.find_one({"_id": ObjectId(role_id)}) if ObjectId.is_valid(role_id) else None
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")

    update: dict = {k: v for k, v in body.model_dump().items() if v is not None}

    if "permissions" in update:
        update["permissions"] = _validate_codes(update["permissions"])

    update["updated_at"] = _now()
    await col.update_one({"_id": doc["_id"]}, {"$set": update})
    updated = await col.find_one({"_id": doc["_id"]})
    return serialize_doc(updated)


# ─── DELETE ───────────────────────────────────────────────────────────────────

@router.delete("/{role_id}", summary="Delete a custom role")
async def delete_role(role_id: str, current_user: dict = Depends(get_current_user)):
    col = _col()
    doc = await col.find_one({"_id": ObjectId(role_id)}) if ObjectId.is_valid(role_id) else None
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    if doc.get("is_predefined"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Predefined system roles cannot be deleted. Disable or clone instead.",
        )
    await col.delete_one({"_id": doc["_id"]})
    return {"message": "Role deleted"}


# ─── ASSIGN role to employee ──────────────────────────────────────────────────

@router.patch(
    "/{role_id}/assign/{employee_id}",
    summary="Assign this role to an employee",
)
async def assign_role_to_employee(
    role_id: str,
    employee_id: str,
    branch_id: str = Query(..., description="Branch context for this assignment"),
    current_user: dict = Depends(get_current_user),
):
    """
    Sets employee.role_id = role_id  and  employee.branch_id = branch_id.
    Branch isolation: the caller token must own this branch unless super admin.
    """
    if not _is_super_admin(current_user):
        token_branch = current_user.get("branch_id") or current_user.get("entity_id") or ""
        if str(token_branch) != str(branch_id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot assign roles in another branch")

    # Verify role exists
    role_col = _col()
    role_doc = await role_col.find_one({"_id": ObjectId(role_id)}) if ObjectId.is_valid(role_id) else None
    if not role_doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")

    # Update employee
    emp_col = db_config.get_collection("employees")
    flt = {"_id": ObjectId(employee_id)} if ObjectId.is_valid(employee_id) else {"emp_id": employee_id}
    emp = await emp_col.find_one(flt)
    if not emp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")

    await emp_col.update_one(flt, {"$set": {
        "role_id": str(role_doc["_id"]),
        "role_name": role_doc.get("name", ""),
        "branch_id": branch_id,
        "updated_at": _now(),
    }})
    return {"message": f"Role '{role_doc['name']}' assigned to employee {employee_id}"}
