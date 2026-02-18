from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.config.database import db_config, Collections
from app.utils.auth import get_current_user
from app.database.db_operations import db_ops
from app.utils.helpers import serialize_doc, serialize_docs
from app.models.hotel_room import HotelRoomCreate, HotelRoomUpdate, HotelRoomResponse

router = APIRouter(prefix="/hotel-rooms", tags=["Hotel Rooms"])

@router.post("/", response_model=HotelRoomResponse, status_code=status.HTTP_201_CREATED)
async def create_hotel_room(
    room: HotelRoomCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new hotel room with strict validation"""
    
    # 1. Verify Floor Exists
    floor = await db_ops.get_by_id(Collections.HOTEL_FLOORS, room.floor_id)
    if not floor:
        raise HTTPException(status_code=404, detail="Floor not found")
    
    # 2. Verify Hotel ID Consistency
    if floor["hotel_id"] != room.hotel_id:
        raise HTTPException(status_code=400, detail="Floor does not belong to the specified hotel")

    # 3. CRITICAL VALIDATION: Verify Bed Type is configured in Hotel Pricing
    hotel = await db_ops.get_by_id(Collections.HOTELS, room.hotel_id)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
        
    prices = hotel.get("prices", [])
    allowed_bed_types = {str(p.get("bed_type_id")) for p in prices if p.get("bed_type_id")}
    
    if room.bed_type_id not in allowed_bed_types:
        raise HTTPException(
            status_code=400, 
            detail="This bed type is not configured in the hotel's pricing. Add pricing for this bed type first."
        )
    
    room_dict = room.model_dump(mode='json')
    created = await db_ops.create(Collections.HOTEL_ROOMS, room_dict)
    return serialize_doc(created)

@router.get("/", response_model=List[HotelRoomResponse])
async def get_hotel_rooms(
    hotel_id: str = None,
    floor_id: str = None,
    is_active: bool = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all hotel rooms with optional filtering"""
    filter_query = {}
    if hotel_id:
        filter_query["hotel_id"] = hotel_id
    if floor_id:
        filter_query["floor_id"] = floor_id
    if is_active is not None:
        filter_query["is_active"] = is_active
        
    rooms = await db_ops.get_all(Collections.HOTEL_ROOMS, filter_query)
    
    # Sort by room_number
    sorted_rooms = sorted(rooms, key=lambda r: r.get('room_number', ''))
    return serialize_docs(sorted_rooms)

@router.get("/{room_id}", response_model=HotelRoomResponse)
async def get_hotel_room(
    room_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get hotel room by ID"""
    room = await db_ops.get_by_id(Collections.HOTEL_ROOMS, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Hotel room not found")
    return serialize_doc(room)

@router.put("/{room_id}", response_model=HotelRoomResponse)
async def update_hotel_room(
    room_id: str,
    room_update: HotelRoomUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update hotel room"""
    
    # If bed_type_id is changing, must validate against hotel pricing again
    if room_update.bed_type_id:
        current_room = await db_ops.get_by_id(Collections.HOTEL_ROOMS, room_id)
        if not current_room:
             raise HTTPException(status_code=404, detail="Hotel room not found")
             
        hotel = await db_ops.get_by_id(Collections.HOTELS, current_room["hotel_id"])
        
        prices = hotel.get("prices", [])
        allowed_bed_types = {str(p.get("bed_type_id")) for p in prices if p.get("bed_type_id")}
        
        if room_update.bed_type_id not in allowed_bed_types:
             raise HTTPException(
                status_code=400, 
                detail="This bed type is not configured in the hotel's pricing."
            )

    update_data = room_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
        
    updated = await db_ops.update(Collections.HOTEL_ROOMS, room_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Hotel room not found")
    return serialize_doc(updated)

@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hotel_room(
    room_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete hotel room"""
    # FUTURE TODO: Check if room has active bookings before deleting
    
    deleted = await db_ops.delete(Collections.HOTEL_ROOMS, room_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Hotel room not found")
