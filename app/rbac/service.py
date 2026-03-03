"""
RBAC Service – Permission Resolution Engine
============================================

Resolution order for any permission check
------------------------------------------
1. Super Admin (JWT sub field)  → ALLOW always
2. Branch Manager role          → ALLOW always within own branch
3. employee_permission_overrides.revoked contains code → DENY
4. employee_permission_overrides.granted contains code  → ALLOW
5. employee's assigned branch_role.permissions contains code → ALLOW
6. default                                               → DENY

Branch isolation:
  Every query is scoped by (organization_id, branch_id).
  Cross-branch access is blocked at the DB filter level.

Usage (FastAPI dependency example):
    from app.rbac.service import require_permission
    
    @router.get("/payments")
    async def list_payments(
        _: None = Depends(require_permission("payments.view")),
        current_user = Depends(get_current_user),
    ):
        ...
"""
from __future__ import annotations
import sys
from functools import lru_cache
from typing import Dict, List, Optional, Set, Tuple

from fastapi import Depends, HTTPException, status
from bson import ObjectId

from app.config.database import db_config
from app.utils.auth import get_current_user
from app.rbac.permissions import PREDEFINED_ROLES, ALL_PERMISSION_CODES


# ─── Collection name constants ────────────────────────────────────────────────
_COL_ROLES   = "branch_roles"
_COL_OVR     = "employee_permission_overrides"
_COL_EMP     = "employees"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _is_super_admin(user: Dict) -> bool:
    """True when the JWT belongs to a platform-level super admin."""
    return bool(user.get("sub"))


def _is_branch_manager_role(role_doc: Optional[Dict]) -> bool:
    return bool(role_doc and role_doc.get("predefined_key") == "branch_manager")


async def _get_employee(emp_id: str) -> Optional[Dict]:
    col = db_config.get_collection(_COL_EMP)
    # Try both _id (ObjectId) and emp_id (string)
    emp = None
    if ObjectId.is_valid(emp_id):
        emp = await col.find_one({"_id": ObjectId(emp_id)})
    if not emp:
        emp = await col.find_one({"emp_id": emp_id})
    return emp


async def _get_role(role_id: str) -> Optional[Dict]:
    col = db_config.get_collection(_COL_ROLES)
    if ObjectId.is_valid(role_id):
        return await col.find_one({"_id": ObjectId(role_id)})
    return await col.find_one({"_id": role_id})


async def _get_override(employee_id: str, branch_id: str) -> Optional[Dict]:
    col = db_config.get_collection(_COL_OVR)
    return await col.find_one({
        "employee_id": employee_id,
        "branch_id": branch_id,
    })


# ─── Core resolver ───────────────────────────────────────────────────────────

async def resolve_permissions(
    employee_id: str,
    branch_id: str,
    organization_id: str,
) -> Tuple[Set[str], str]:
    """
    Compute the effective permissions for ``employee_id`` in ``branch_id``.

    Returns:
        (effective_set, source)
        source: 'branch_manager' | 'role' | 'override' | 'none'
    """
    emp = await _get_employee(employee_id)
    if not emp:
        return set(), "none"

    # ── enforce branch isolation ──────────────────────────────────────────────
    if emp.get("entity_type") == "branch":
        if str(emp.get("entity_id", "")) != str(branch_id):
            return set(), "none"  # wrong branch → no permissions

    role_id = str(emp.get("role_id", ""))
    role_doc = await _get_role(role_id) if role_id else None

    # Branch Manager → all permissions in this branch
    if _is_branch_manager_role(role_doc):
        return set(ALL_PERMISSION_CODES), "branch_manager"

    # Base permissions from assigned role
    role_perms: Set[str] = set()
    if role_doc:
        raw = role_doc.get("permissions") or []
        # If predefined and no custom list stored, fall back to template
        if not raw and role_doc.get("predefined_key") in PREDEFINED_ROLES:
            raw = PREDEFINED_ROLES[role_doc["predefined_key"]]
        role_perms = set(raw)

    # Apply per-employee overrides
    override_doc = await _get_override(employee_id, branch_id)
    if override_doc:
        granted: Set[str] = set(override_doc.get("granted") or [])
        revoked: Set[str] = set(override_doc.get("revoked") or [])
        effective = (role_perms | granted) - revoked
        return effective, "override"

    return role_perms, "role"


async def has_permission(
    employee_id: str,
    branch_id: str,
    organization_id: str,
    permission: str,
) -> bool:
    """
    Returns True if the employee holds ``permission`` in ``branch_id``.
    Wildcard check: 'payments.*' grants all payments.* codes.
    """
    effective, _ = await resolve_permissions(employee_id, branch_id, organization_id)
    if permission in effective:
        return True
    # Support wildcard segments: bookings.* matches bookings.ticket.view etc.
    prefix = ".".join(permission.split(".")[:-1])
    return f"{prefix}.*" in effective


# ─── FastAPI dependency factory ───────────────────────────────────────────────

def require_permission(permission_code: str):
    """
    FastAPI dependency factory.

    Usage:
        @router.get("/payments")
        async def list_payments(
            _: None = Depends(require_permission("payments.view")),
            current_user = Depends(get_current_user),
        ):
            ...

    The dependency reads employee_id, branch_id, org_id from the JWT payload.
    """
    async def _dep(current_user: Dict = Depends(get_current_user)) -> None:
        # ── Super admin bypasses all checks ──────────────────────────────────
        if _is_super_admin(current_user):
            return

        emp_id  = current_user.get("emp_id") or current_user.get("_id") or ""
        branch  = current_user.get("branch_id") or current_user.get("entity_id") or ""
        org     = current_user.get("organization_id") or ""

        if not emp_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No employee identity in token")
        if not branch:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No branch context in token")

        granted = await has_permission(emp_id, branch, org, permission_code)
        if not granted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: '{permission_code}' is required",
            )

    return _dep


def require_any_permission(*permission_codes: str):
    """Allow access if the employee has at least ONE of the given permissions."""
    async def _dep(current_user: Dict = Depends(get_current_user)) -> None:
        if _is_super_admin(current_user):
            return
        emp_id = current_user.get("emp_id") or current_user.get("_id") or ""
        branch = current_user.get("branch_id") or current_user.get("entity_id") or ""
        org    = current_user.get("organization_id") or ""
        if not emp_id or not branch:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing identity/branch context")
        effective, _ = await resolve_permissions(emp_id, branch, org)
        if not any(p in effective for p in permission_codes):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"Need one of: {list(permission_codes)}",
            )
    return _dep


# ─── Branch isolation dependency ─────────────────────────────────────────────

async def enforce_branch_scope(current_user: Dict = Depends(get_current_user)) -> str:
    """
    Returns the branch_id the current user is allowed to see.
    Super admin can pass ?branch_id= query param freely; branch employees are
    locked to their own branch_id from the token.
    """
    if _is_super_admin(current_user):
        # Super admin: branch_id is optional (passed via query param)
        return current_user.get("branch_id") or ""

    branch = current_user.get("branch_id") or current_user.get("entity_id") or ""
    if not branch:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Branch employees must have a branch_id in their token",
        )
    return branch


# ─── Seed predefined roles for an org/branch ─────────────────────────────────

async def seed_predefined_roles(organization_id: str, branch_id: Optional[str] = None):
    """
    Create the 5 predefined role documents for the given org/branch if they
    don't already exist.  Call this after creating an org or branch.
    """
    from datetime import datetime

    col = db_config.get_collection(_COL_ROLES)
    now = datetime.utcnow()

    role_display = {
        "hr":              "HR",
        "sales":           "Sales",
        "accountant":      "Accountant",
        "branch_manager":  "Branch Manager",
        "admin":           "Admin",
    }

    for key, perms in PREDEFINED_ROLES.items():
        query: Dict = {
            "organization_id": organization_id,
            "predefined_key": key,
        }
        if branch_id:
            query["branch_id"] = branch_id

        existing = await col.find_one(query)
        if not existing:
            doc = {
                **query,
                "name": role_display.get(key, key.title()),
                "is_predefined": True,
                "permissions": perms,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            await col.insert_one(doc)
            print(f"  seeded role '{key}' for org={organization_id} branch={branch_id}", file=sys.stderr)
