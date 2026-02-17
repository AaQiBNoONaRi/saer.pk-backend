from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.config.database import db_config, Collections
from app.utils.auth import get_current_user
from app.database.db_operations import db_ops
from app.utils.helpers import serialize_doc, serialize_docs
from app.models.hotel_category import HotelCategoryCreate, HotelCategoryUpdate, HotelCategoryResponse

router = APIRouter(prefix="/hotel-categories", tags=["Hotel Categories"])

@router.post("/", response_model=HotelCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_hotel_category(
    category: HotelCategoryCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new hotel category"""
    category_dict = category.model_dump()
    created = await db_ops.create(Collections.HOTEL_CATEGORIES, category_dict)
    return serialize_doc(created)

@router.get("/", response_model=List[HotelCategoryResponse])
async def get_hotel_categories(
    is_active: bool = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all hotel categories"""
    filter_query = {}
    if is_active is not None:
        filter_query["is_active"] = is_active
    categories = await db_ops.get_all(Collections.HOTEL_CATEGORIES, filter_query)
    return serialize_docs(categories)

@router.get("/{category_id}", response_model=HotelCategoryResponse)
async def get_hotel_category(
    category_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get hotel category by ID"""
    category = await db_ops.get_by_id(Collections.HOTEL_CATEGORIES, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Hotel category not found")
    return serialize_doc(category)

@router.put("/{category_id}", response_model=HotelCategoryResponse)
async def update_hotel_category(
    category_id: str,
    category_update: HotelCategoryUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update hotel category"""
    update_data = category_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await db_ops.update(Collections.HOTEL_CATEGORIES, category_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Hotel category not found")
    return serialize_doc(updated)

@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hotel_category(
    category_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete hotel category"""
    deleted = await db_ops.delete(Collections.HOTEL_CATEGORIES, category_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Hotel category not found")
