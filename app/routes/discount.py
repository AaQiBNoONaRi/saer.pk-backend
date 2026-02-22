"""
Discount routes
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.models.discount import DiscountCreate, DiscountUpdate, DiscountResponse
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user

router = APIRouter(prefix="/discounts", tags=["Discounts"])

@router.post("/", response_model=DiscountResponse, status_code=status.HTTP_201_CREATED)
async def create_discount(
    discount: DiscountCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new discount"""
    discount_dict = discount.model_dump(mode='json')
    print(f"DEBUG: Creating discount with data: {discount_dict}")
    print(f"  - ticket_discount: {discount_dict.get('ticket_discount')}")
    print(f"  - ticket_discount_type: {discount_dict.get('ticket_discount_type')}")
    print(f"  - package_discount: {discount_dict.get('package_discount')}")
    print(f"  - package_discount_type: {discount_dict.get('package_discount_type')}")
    created_discount = await db_ops.create(Collections.DISCOUNTS, discount_dict)
    return serialize_doc(created_discount)

@router.get("/", response_model=List[DiscountResponse])
async def get_discounts(
    skip: int = 0,
    limit: int = 100,
    is_active: bool = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all discounts with optional filtering"""
    filter_query = {}
    if is_active is not None:
        filter_query["is_active"] = is_active
    
    discounts = await db_ops.get_all(Collections.DISCOUNTS, filter_query=filter_query, skip=skip, limit=limit)
    print(f"DEBUG: Fetched {len(discounts)} discounts from database")
    result = serialize_docs(discounts)
    print(f"DEBUG: Serialized to {len(result)} documents")
    return result

@router.get("/{discount_id}", response_model=DiscountResponse)
async def get_discount(
    discount_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get discount by ID"""
    discount = await db_ops.get_by_id(Collections.DISCOUNTS, discount_id)
    if not discount:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discount not found"
        )
    return serialize_doc(discount)

@router.put("/{discount_id}", response_model=DiscountResponse)
async def update_discount(
    discount_id: str,
    discount_update: DiscountUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update discount"""
    update_data = discount_update.model_dump(exclude_unset=True, mode='json')
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    updated_discount = await db_ops.update(Collections.DISCOUNTS, discount_id, update_data)
    if not updated_discount:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discount not found"
        )
    
    return serialize_doc(updated_discount)

@router.delete("/{discount_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_discount(
    discount_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete discount"""
    success = await db_ops.delete(Collections.DISCOUNTS, discount_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discount not found"
        )
    return None
