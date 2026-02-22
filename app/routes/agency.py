"""
Agency routes
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.models.agency import AgencyCreate, AgencyUpdate, AgencyResponse
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs, calculate_available_credit
from app.utils.auth import get_current_user, require_org_admin, require_branch_admin

router = APIRouter(prefix="/agencies", tags=["Agencies"])

@router.post("/", response_model=AgencyResponse, status_code=status.HTTP_201_CREATED)
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
    
    agency_dict = agency.model_dump()
    created_agency = await db_ops.create(Collections.AGENCIES, agency_dict)
    
    # Add available_credit field
    created_agency["available_credit"] = calculate_available_credit(
        created_agency["credit_limit"],
        created_agency["credit_used"]
    )
    
    return serialize_doc(created_agency)

@router.get("/", response_model=List[AgencyResponse])
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
    
    # Add available_credit to each agency
    for agency in agencies:
        agency["available_credit"] = calculate_available_credit(
            agency.get("credit_limit", 0),
            agency.get("credit_used", 0)
        )
    
    return serialize_docs(agencies)

@router.get("/{agency_id}", response_model=AgencyResponse)
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
    
    # Add available_credit
    agency["available_credit"] = calculate_available_credit(
        agency.get("credit_limit", 0),
        agency.get("credit_used", 0)
    )
    
    return serialize_doc(agency)

@router.put("/{agency_id}", response_model=AgencyResponse)
async def update_agency(
    agency_id: str,
    agency_update: AgencyUpdate,
    current_user: dict = Depends(require_branch_admin)
):
    """Update agency (Branch Admin or higher)"""
    update_data = agency_update.model_dump(exclude_unset=True)
    
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
    
    # Add available_credit
    updated_agency["available_credit"] = calculate_available_credit(
        updated_agency.get("credit_limit", 0),
        updated_agency.get("credit_used", 0)
    )
    
    return serialize_doc(updated_agency)

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
