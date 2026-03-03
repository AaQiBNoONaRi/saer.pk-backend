"""
RBAC Pydantic Models
====================
Mirrors MongoDB document structure for:

  branch_roles                – role definitions scoped to org/branch
  employee_permission_overrides – per-employee permission mutations
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────────
#  BranchRole  (collection: branch_roles)
# ─────────────────────────────────────────────────────────────────────────────
VALID_PREDEFINED_ROLES = Literal["hr", "sales", "accountant", "branch_manager", "admin"]


class BranchRoleBase(BaseModel):
    organization_id: str = Field(..., description="Parent organization")
    branch_id: Optional[str] = Field(
        None,
        description="Scope this role to one branch; None = org-wide template",
    )
    name: str = Field(..., min_length=1, max_length=100, description="Display name: HR, Sales …")
    is_predefined: bool = Field(
        False,
        description="True for system-seeded roles; these cannot be deleted",
    )
    predefined_key: Optional[str] = Field(
        None, description="Key into PREDEFINED_ROLES dict: hr, sales, accountant …"
    )
    permissions: List[str] = Field(
        default_factory=list,
        description="Flat list of permission codes e.g. ['bookings.ticket.view', ...]",
    )
    is_active: bool = True


class BranchRoleCreate(BranchRoleBase):
    pass


class BranchRoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    branch_id: Optional[str] = None
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None


class BranchRoleResponse(BranchRoleBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}


# ─────────────────────────────────────────────────────────────────────────────
#  EmployeePermissionOverride  (collection: employee_permission_overrides)
# ─────────────────────────────────────────────────────────────────────────────
class EmployeePermissionOverrideBase(BaseModel):
    employee_id: str = Field(..., description="Employee's _id or emp_id")
    organization_id: str
    branch_id: str = Field(..., description="Branch where this override applies")
    granted: List[str] = Field(
        default_factory=list,
        description="Extra codes granted ON TOP of the role's permissions",
    )
    revoked: List[str] = Field(
        default_factory=list,
        description="Codes explicitly REMOVED from the role's permissions",
    )
    note: Optional[str] = Field(None, max_length=500, description="Reason for override")


class EmployeePermissionOverrideCreate(EmployeePermissionOverrideBase):
    pass


class EmployeePermissionOverrideUpdate(BaseModel):
    granted: Optional[List[str]] = None
    revoked: Optional[List[str]] = None
    note: Optional[str] = None


class EmployeePermissionOverrideResponse(EmployeePermissionOverrideBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}


# ─────────────────────────────────────────────────────────────────────────────
#  AssignRole  – body for PATCH /employees/{id}/role
# ─────────────────────────────────────────────────────────────────────────────
class AssignRoleRequest(BaseModel):
    role_id: str = Field(..., description="_id of the BranchRole document")
    branch_id: str = Field(..., description="Branch context for the assignment")


# ─────────────────────────────────────────────────────────────────────────────
#  PermissionCheck response helper
# ─────────────────────────────────────────────────────────────────────────────
class PermissionCheckResult(BaseModel):
    employee_id: str
    branch_id: str
    permission: str
    granted: bool
    source: Literal["super_admin", "branch_manager", "override_granted", "role", "denied"]
