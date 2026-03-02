"""
Commission routes
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from app.models.commission import CommissionCreate, CommissionUpdate, CommissionResponse
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user, get_org_id

router = APIRouter(prefix="/commissions", tags=["Commissions"])

@router.post("/", response_model=CommissionResponse, status_code=status.HTTP_201_CREATED)
async def create_commission(
    commission: CommissionCreate,
    org_id: str = Depends(get_org_id),
):
    """Create a new commission – stamped with caller's org"""
    commission_dict = commission.model_dump(mode='json')
    commission_dict["organization_id"] = org_id
    created_commission = await db_ops.create(Collections.COMMISSIONS, commission_dict)
    return serialize_doc(created_commission)

@router.get("/", response_model=List[CommissionResponse])
async def get_commissions(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = Query(None, alias="status"),
    partner_type: Optional[str] = None,
    org_id: str = Depends(get_org_id),
):
    """Get commissions scoped to caller's org"""
    filter_query: dict = {"organization_id": org_id}
    if status_filter:
        filter_query["status"] = status_filter
    if partner_type:
        filter_query["partner_type"] = partner_type
    
    commissions = await db_ops.get_all(Collections.COMMISSIONS, filter_query=filter_query, skip=skip, limit=limit)
    return serialize_docs(commissions)

@router.get("/{commission_id}", response_model=CommissionResponse)
async def get_commission(
    commission_id: str,
    org_id: str = Depends(get_org_id),
):
    """Get commission by ID – ownership check"""
    commission = await db_ops.get_by_id(Collections.COMMISSIONS, commission_id)
    if not commission or commission.get("organization_id") != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commission not found")
    return serialize_doc(commission)

@router.put("/{commission_id}", response_model=CommissionResponse)
async def update_commission(
    commission_id: str,
    commission_update: CommissionUpdate,
    org_id: str = Depends(get_org_id),
):
    """Update commission – ownership check"""
    commission = await db_ops.get_by_id(Collections.COMMISSIONS, commission_id)
    if not commission or commission.get("organization_id") != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commission not found")
    update_data = commission_update.model_dump(exclude_unset=True, mode='json')
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    updated_commission = await db_ops.update(Collections.COMMISSIONS, commission_id, update_data)
    return serialize_doc(updated_commission)

@router.delete("/{commission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_commission(
    commission_id: str,
    org_id: str = Depends(get_org_id),
):
    """Delete commission – ownership check"""
    commission = await db_ops.get_by_id(Collections.COMMISSIONS, commission_id)
    if not commission or commission.get("organization_id") != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commission not found")
    await db_ops.delete(Collections.COMMISSIONS, commission_id)
    return None
