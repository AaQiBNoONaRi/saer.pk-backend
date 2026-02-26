"""
Branch routes
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from pydantic import BaseModel
from app.models.branch import BranchCreate, BranchUpdate, BranchResponse
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user, require_org_admin, hash_password

router = APIRouter(prefix="/branches", tags=["Branches"])

@router.post("/", response_model=BranchResponse, status_code=status.HTTP_201_CREATED)
async def create_branch(
    branch: BranchCreate,
    current_user: dict = Depends(require_org_admin)
):
    """Create a new branch (Org Admin only)"""
    # Verify organization exists
    org = await db_ops.get_by_id(Collections.ORGANIZATIONS, branch.organization_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Check if branch with same email already exists
    existing = await db_ops.get_one(Collections.BRANCHES, {"email": branch.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Branch with this email already exists"
        )
    
    branch_dict = branch.model_dump()
    
    # Hash password if present
    if "password" in branch_dict and branch_dict["password"]:
        branch_dict["password"] = hash_password(branch_dict["password"])
        
    created_branch = await db_ops.create(Collections.BRANCHES, branch_dict)
    return serialize_doc(created_branch)

@router.get("/", response_model=List[BranchResponse])
async def get_branches(
    organization_id: str = None,
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get all branches, optionally filtered by organization"""
    filter_query = {"organization_id": organization_id} if organization_id else {}
    branches = await db_ops.get_all(Collections.BRANCHES, filter_query, skip=skip, limit=limit)
    
    # Populate groups for each branch
    for branch in branches:
        # Populate commission group
        if branch.get("commission_group_id"):
            commission_group = await db_ops.get_by_id(Collections.COMMISSIONS, branch["commission_group_id"])
            if commission_group:
                branch["commission_group"] = serialize_doc(commission_group)
        
        # Populate service charge group
        if branch.get("service_charge_group_id"):
            service_charge_group = await db_ops.get_by_id(Collections.SERVICE_CHARGES, branch["service_charge_group_id"])
            if service_charge_group:
                branch["service_charge_group"] = serialize_doc(service_charge_group)
    
    return serialize_docs(branches)

@router.get("/{branch_id}", response_model=BranchResponse)
async def get_branch(
    branch_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get branch by ID"""
    branch = await db_ops.get_by_id(Collections.BRANCHES, branch_id)
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found"
        )
    
    # Populate commission group
    if branch.get("commission_group_id"):
        commission_group = await db_ops.get_by_id(Collections.COMMISSIONS, branch["commission_group_id"])
        if commission_group:
            branch["commission_group"] = serialize_doc(commission_group)
    
    # Populate service charge group
    if branch.get("service_charge_group_id"):
        service_charge_group = await db_ops.get_by_id(Collections.SERVICE_CHARGES, branch["service_charge_group_id"])
        if service_charge_group:
            branch["service_charge_group"] = serialize_doc(service_charge_group)
    
    return serialize_doc(branch)

@router.put("/{branch_id}", response_model=BranchResponse)
async def update_branch(
    branch_id: str,
    branch_update: BranchUpdate,
    current_user: dict = Depends(require_org_admin)
):
    """Update branch (Org Admin only)"""
    update_data = branch_update.model_dump(exclude_unset=True)
    
    # Hash password if present
    if "password" in update_data and update_data["password"]:
        update_data["password"] = hash_password(update_data["password"])
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    updated_branch = await db_ops.update(Collections.BRANCHES, branch_id, update_data)
    if not updated_branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found"
        )
    
    return serialize_doc(updated_branch)

class BranchPasswordSet(BaseModel):
    password: str

@router.post("/{branch_id}/set-password", response_model=BranchResponse)
async def set_branch_password(
    branch_id: str,
    data: BranchPasswordSet,
    current_user: dict = Depends(require_org_admin)
):
    """Set or reset a branch portal password (Org Admin only)"""
    if not data.password or len(data.password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 4 characters"
        )
    
    hashed = hash_password(data.password)
    updated_branch = await db_ops.update(
        Collections.BRANCHES,
        branch_id,
        {"password": hashed, "portal_access_enabled": True}
    )
    if not updated_branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found"
        )
    
    return serialize_doc(updated_branch)

@router.delete("/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_branch(
    branch_id: str,
    current_user: dict = Depends(require_org_admin)
):
    """Delete branch (Org Admin only)"""
    deleted = await db_ops.delete(Collections.BRANCHES, branch_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found"
        )
