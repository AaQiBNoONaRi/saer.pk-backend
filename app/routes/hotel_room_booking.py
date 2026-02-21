from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import date
from bson import ObjectId
from app.config.database import db_config, Collections
from app.utils.auth import get_current_user
from app.database.db_operations import db_ops
from app.utils.helpers import serialize_doc, serialize_docs
from app.models.hotel_room_booking import HotelRoomBookingCreate, HotelRoomBookingUpdate, HotelRoomBookingResponse

router = APIRouter(prefix="/hotel-bookings", tags=["Hotel Bookings"])

@router.post("/", response_model=HotelRoomBookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking(
    booking: HotelRoomBookingCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new room booking with double-booking prevention"""
    
    # 1. Validation: End date must be after start date
    if booking.date_to < booking.date_from:
         raise HTTPException(status_code=400, detail="End date must be after start date")

    # 2. Validation: Room must exist
    room = await db_ops.get_by_id(Collections.HOTEL_ROOMS, booking.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
        
    # 3. Validation: Hotel ID Match
    if room["hotel_id"] != booking.hotel_id:
        raise HTTPException(status_code=400, detail="Room does not belong to specified hotel")
        
    # 4. CRITICAL: Double Booking Check
    # Check if any active booking overlaps with requested range
    # Overlap logic: (StartA <= EndB) and (EndA >= StartB)
    existing_booking = await db_ops.get_all(Collections.HOTEL_ROOM_BOOKINGS, {
        "room_id": booking.room_id,
        "status": {"$in": ["BOOKED", "CHECKED_IN"]}, # Ignore Cancelled/CheckedOut
        "$or": [
            {
                "date_from": {"$lte": booking.date_to.isoformat()},
                "date_to": {"$gte": booking.date_from.isoformat()}
            }
        ]
    }, limit=1)
    
    if existing_booking:
        raise HTTPException(
            status_code=409, 
            detail="Room is already booked for the selected dates."
        )
        
    # Create booking
    booking_dict = booking.model_dump(mode='json')
    created = await db_ops.create(Collections.HOTEL_ROOM_BOOKINGS, booking_dict)
    
    # Update Room Status (Optional/Optimistic - keep it simple for now, reliance on booking table)
    # await db_ops.update(Collections.HOTEL_ROOMS, booking.room_id, {"status": "BOOKED"}) 
    
    return serialize_doc(created)

@router.get("/", response_model=List[HotelRoomBookingResponse])
async def get_bookings(
    hotel_id: str = None,
    room_id: str = None,
    client_name: str = None,
    date_from: date = None, 
    date_to: date = None,
    status_filter: str = None,
    current_user: dict = Depends(get_current_user)
):
    """Get bookings with filters"""
    filter_query = {}
    if hotel_id:
        filter_query["hotel_id"] = hotel_id
    if room_id:
        filter_query["room_id"] = room_id
    if client_name:
        filter_query["client_name"] = {"$regex": client_name, "$options": "i"}
    if status_filter:
        filter_query["status"] = status_filter
        
    # Date Range Overlap Filter (Find bookings falling within requested range)
    if date_from and date_to:
         filter_query["$or"] = [
            {
                "date_from": {"$lte": date_to.isoformat()},
                "date_to": {"$gte": date_from.isoformat()}
            }
        ]
        
    bookings = await db_ops.get_all(Collections.HOTEL_ROOM_BOOKINGS, filter_query)
    return serialize_docs(bookings)

@router.put("/{booking_id}", response_model=HotelRoomBookingResponse)
async def update_booking(
    booking_id: str,
    booking_update: HotelRoomBookingUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update booking details or status"""
    
    # Fetch existing
    existing = await db_ops.get_by_id(Collections.HOTEL_ROOM_BOOKINGS, booking_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Booking not found")

    # If dates are changing, must re-validate availability (excluding self)
    if booking_update.date_from or booking_update.date_to:
        new_from = booking_update.date_from or date.fromisoformat(existing["date_from"])
        new_to = booking_update.date_to or date.fromisoformat(existing["date_to"])
        
        if new_to < new_from:
             raise HTTPException(status_code=400, detail="End date must be after start date")

        # Double Booking check excluding current ID
        overlap = await db_ops.get_all(Collections.HOTEL_ROOM_BOOKINGS, {
            "_id": {"$ne": ObjectId(booking_id)}, # Exclude self via ObjectId!
            "room_id": existing["room_id"],
            "status": {"$in": ["BOOKED", "CHECKED_IN"]},
            "$or": [
                {
                    "date_from": {"$lte": new_to.isoformat()},
                    "date_to": {"$gte": new_from.isoformat()}
                }
            ]
        }, limit=1)
        
        if overlap:
             raise HTTPException(
                status_code=409, 
                detail="Date change causes overlap with another booking."
            )

    update_data = booking_update.model_dump(mode='json', exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
        
    updated = await db_ops.update(Collections.HOTEL_ROOM_BOOKINGS, booking_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Booking not found or could not be updated")
    
    return serialize_doc(updated)

@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_booking(
    booking_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Cancel/Delete booking"""
    # Better to mark as CANCELLED via update, but support delete if needed
    deleted = await db_ops.delete(Collections.HOTEL_ROOM_BOOKINGS, booking_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Booking not found")
