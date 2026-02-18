from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.config.database import db_config, Collections
from app.utils.auth import get_current_user
from app.database.db_operations import db_ops
from app.utils.helpers import serialize_doc, serialize_docs
from app.models.hotel_floor import HotelFloorCreate, HotelFloorUpdate, HotelFloorResponse

router = APIRouter(prefix="/hotel-floors", tags=["Hotel Floors"])

@router.post("/", response_model=HotelFloorResponse, status_code=status.HTTP_201_CREATED)
async def create_hotel_floor(
    floor: HotelFloorCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new hotel floor"""
    floor_dict = floor.model_dump(mode='json')
    created = await db_ops.create(Collections.HOTEL_FLOORS, floor_dict)
    return serialize_doc(created)

@router.get("/", response_model=List[HotelFloorResponse])
async def get_hotel_floors(
    hotel_id: str = None,
    is_active: bool = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all hotel floors, optionally filtered by hotel"""
    filter_query = {}
    if hotel_id:
        filter_query["hotel_id"] = hotel_id
    if is_active is not None:
        filter_query["is_active"] = is_active
        
    floors = await db_ops.get_all(Collections.HOTEL_FLOORS, filter_query)
    
    # Sort by floor_number (numeric check then string)
    def floor_sort_key(f):
        try:
            return float(f.get('floor_number', 0))
        except ValueError:
            return f.get('floor_number', '')
            
    sorted_floors = sorted(floors, key=floor_sort_key)
    return serialize_docs(sorted_floors)

@router.get("/{floor_id}", response_model=HotelFloorResponse)
async def get_hotel_floor(
    floor_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get hotel floor by ID"""
    floor = await db_ops.get_by_id(Collections.HOTEL_FLOORS, floor_id)
    if not floor:
        raise HTTPException(status_code=404, detail="Hotel floor not found")
    return serialize_doc(floor)

@router.put("/{floor_id}", response_model=HotelFloorResponse)
async def update_hotel_floor(
    floor_id: str,
    floor_update: HotelFloorUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update hotel floor"""
    update_data = floor_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await db_ops.update(Collections.HOTEL_FLOORS, floor_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Hotel floor not found")
    return serialize_doc(updated)

@router.delete("/{floor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hotel_floor(
    floor_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete hotel floor. Cannot delete if rooms exist."""
    
    # Validation: Check if rooms exist on this floor
    rooms = await db_ops.get_all(Collections.HOTEL_ROOMS, {"floor_id": floor_id}, limit=1)
    if rooms:
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete floor because it contains rooms. Delete rooms first."
        )
        
    deleted = await db_ops.delete(Collections.HOTEL_FLOORS, floor_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Hotel floor not found")
