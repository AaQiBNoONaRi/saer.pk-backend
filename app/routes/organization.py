"""
Organization routes
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
import bcrypt
from app.models.organization import OrganizationCreate, OrganizationUpdate, OrganizationResponse
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user, require_org_admin

router = APIRouter(prefix="/organizations", tags=["Organizations"])

@router.post("/", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    org: OrganizationCreate,
    current_user: dict = Depends(require_org_admin)
):
    """Create a new organization (Org Admin only)"""
    # Check if organization with same email already exists
    existing = await db_ops.get_one(Collections.ORGANIZATIONS, {"email": org.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization with this email already exists"
        )
    
    org_dict = org.model_dump()
    
    # Hash password if portal access is enabled and password is provided
    if org_dict.get('portal_access_enabled') and org_dict.get('password'):
        hashed_password = bcrypt.hashpw(
            org_dict['password'].encode('utf-8'),
            bcrypt.gensalt()
        )
        org_dict['password'] = hashed_password.decode('utf-8')
    elif org_dict.get('portal_access_enabled'):
        # If portal access enabled but no password, raise error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is required when portal access is enabled"
        )
    
    created_org = await db_ops.create(Collections.ORGANIZATIONS, org_dict)
    return serialize_doc(created_org)

@router.get("/", response_model=List[OrganizationResponse])
async def get_organizations(
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get all organizations"""
    organizations = await db_ops.get_all(Collections.ORGANIZATIONS, skip=skip, limit=limit)
    return serialize_docs(organizations)

@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get organization by ID"""
    organization = await db_ops.get_by_id(Collections.ORGANIZATIONS, org_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    return serialize_doc(organization)

@router.put("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: str,
    org_update: OrganizationUpdate,
    current_user: dict = Depends(require_org_admin)
):
    """Update organization (Org Admin only)"""
    update_data = org_update.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    # Hash password if it's being updated
    if 'password' in update_data and update_data['password']:
        hashed_password = bcrypt.hashpw(
            update_data['password'].encode('utf-8'),
            bcrypt.gensalt()
        )
        update_data['password'] = hashed_password.decode('utf-8')
    
    updated_org = await db_ops.update(Collections.ORGANIZATIONS, org_id, update_data)
    if not updated_org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    return serialize_doc(updated_org)

@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: str,
    current_user: dict = Depends(require_org_admin)
):
    """Delete organization (Org Admin only)"""
    deleted = await db_ops.delete(Collections.ORGANIZATIONS, org_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
