"""
Agency routes
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.models.agency import AgencyCreate, AgencyUpdate
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs, calculate_available_credit
from app.utils.auth import get_current_user, require_org_admin, require_branch_admin, hash_password

router = APIRouter(prefix="/agencies", tags=["Agencies"])

def add_available_credit(agency_doc):
    """Safely add available_credit to an agency document"""
    try:
        limit = float(agency_doc.get("credit_limit") or 0)
        used = float(agency_doc.get("credit_used") or 0)
        agency_doc["available_credit"] = calculate_available_credit(limit, used)
    except Exception:
        agency_doc["available_credit"] = 0.0
    # Remove password from response
    agency_doc.pop("password", None)
    return agency_doc

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_agency(
    agency: AgencyCreate,
    current_user: dict = Depends(require_org_admin)
):
    """Create a new agency (Org Admin only)"""
    # Verify organization exists
    org = await db_ops.get_by_id(Collections.ORGANIZATIONS, agency.organization_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Verify branch exists
    branch = await db_ops.get_by_id(Collections.BRANCHES, agency.branch_id)
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found"
        )
    
    # Check if agency with same email already exists
    existing = await db_ops.get_one(Collections.AGENCIES, {"email": agency.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agency with this email already exists"
        )
    
    # Validate password when portal access is enabled
    if agency.portal_access_enabled and not agency.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is required when portal access is enabled"
        )
    
    agency_dict = agency.model_dump()
    
    # Hash password if provided
    if "password" in agency_dict and agency_dict["password"]:
        agency_dict["password"] = hash_password(agency_dict["password"])
    else:
        # Remove password field if not provided
        agency_dict.pop("password", None)
        
    created_agency = await db_ops.create(Collections.AGENCIES, agency_dict)
    
    return add_available_credit(serialize_doc(created_agency))

@router.get("/")
async def get_agencies(
    organization_id: str = None,
    branch_id: str = None,
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get all agencies, optionally filtered by organization or branch"""
    filter_query = {}
    if organization_id:
        filter_query["organization_id"] = organization_id
    if branch_id:
        filter_query["branch_id"] = branch_id
    
    agencies = await db_ops.get_all(Collections.AGENCIES, filter_query, skip=skip, limit=limit)
    
    result = []
    for agency in agencies:
        doc = serialize_doc(agency)
        add_available_credit(doc)
        result.append(doc)
    
    return result

@router.get("/{agency_id}")
async def get_agency(
    agency_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get agency by ID"""
    agency = await db_ops.get_by_id(Collections.AGENCIES, agency_id)
    if not agency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found"
        )
    
    return add_available_credit(serialize_doc(agency))

@router.put("/{agency_id}")
async def update_agency(
    agency_id: str,
    agency_update: AgencyUpdate,
    current_user: dict = Depends(require_branch_admin)
):
    """Update agency (Branch Admin or higher)"""
    update_data = agency_update.model_dump(exclude_unset=True)
    
    # Hash password if present
    if "password" in update_data and update_data["password"]:
        update_data["password"] = hash_password(update_data["password"])
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    updated_agency = await db_ops.update(Collections.AGENCIES, agency_id, update_data)
    if not updated_agency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found"
        )
    
    return add_available_credit(serialize_doc(updated_agency))

@router.delete("/{agency_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agency(
    agency_id: str,
    current_user: dict = Depends(require_org_admin)
):
    """Delete agency (Org Admin only)"""
    deleted = await db_ops.delete(Collections.AGENCIES, agency_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found"
        )