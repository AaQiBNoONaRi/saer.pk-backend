"""
Discount routes
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.models.discount import DiscountCreate, DiscountUpdate, DiscountResponse
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user, get_org_id

router = APIRouter(prefix="/discounts", tags=["Discounts"])

@router.post("/", response_model=DiscountResponse, status_code=status.HTTP_201_CREATED)
async def create_discount(
    discount: DiscountCreate,
    org_id: str = Depends(get_org_id),
):
    """Create a new discount – stamped with caller's org"""
    discount_dict = discount.model_dump(mode='json')
    discount_dict["organization_id"] = org_id
    created_discount = await db_ops.create(Collections.DISCOUNTS, discount_dict)
    return serialize_doc(created_discount)

@router.get("/", response_model=List[DiscountResponse])
async def get_discounts(
    skip: int = 0,
    limit: int = 100,
    is_active: bool = None,
    org_id: str = Depends(get_org_id),
):
    """Get discounts scoped to caller's org"""
    filter_query: dict = {"organization_id": org_id}
    if is_active is not None:
        filter_query["is_active"] = is_active
    discounts = await db_ops.get_all(Collections.DISCOUNTS, filter_query=filter_query, skip=skip, limit=limit)
    return serialize_docs(discounts)

@router.get("/{discount_id}", response_model=DiscountResponse)
async def get_discount(
    discount_id: str,
    org_id: str = Depends(get_org_id),
):
    discount = await db_ops.get_by_id(Collections.DISCOUNTS, discount_id)
    if not discount or discount.get("organization_id") != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discount not found")
    return serialize_doc(discount)

@router.put("/{discount_id}", response_model=DiscountResponse)
async def update_discount(
    discount_id: str,
    discount_update: DiscountUpdate,
    org_id: str = Depends(get_org_id),
):
    discount = await db_ops.get_by_id(Collections.DISCOUNTS, discount_id)
    if not discount or discount.get("organization_id") != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discount not found")
    update_data = discount_update.model_dump(exclude_unset=True, mode='json')
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    updated_discount = await db_ops.update(Collections.DISCOUNTS, discount_id, update_data)
    return serialize_doc(updated_discount)

@router.delete("/{discount_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_discount(
    discount_id: str,
    org_id: str = Depends(get_org_id),
):
    discount = await db_ops.get_by_id(Collections.DISCOUNTS, discount_id)
    if not discount or discount.get("organization_id") != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discount not found")
    await db_ops.delete(Collections.DISCOUNTS, discount_id)
    return None
