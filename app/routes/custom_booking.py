"""
Custom Package Booking routes - Dedicated API for custom package bookings
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from datetime import datetime
import random
import string
from app.models.booking import BookingCreate, BookingUpdate, BookingResponse
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user

router = APIRouter(prefix="/custom-bookings", tags=["Custom Bookings"])

def generate_booking_reference():
    """Generate unique booking reference like CB-YYMMDD-XXXX"""
    timestamp = datetime.now().strftime('%y%m%d')
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"CB-{timestamp}-{random_str}"

@router.post("/", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_booking(
    booking: BookingCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new custom package booking"""
    
    # Verify custom package exists
    package = await db_ops.get_by_id(Collections.PACKAGES, booking.ticket_id)
    if not package:
        raise HTTPException(status_code=404, detail="Custom package not found")
    
    if not package.get('is_active', False):
        raise HTTPException(status_code=400, detail="Custom package is not active")
    
    available_seats = package.get('available_seats', 0)
    if available_seats < booking.total_passengers:
        raise HTTPException(
            status_code=400, 
            detail=f"Not enough seats available. Only {available_seats} seats left."
        )
    
    # Prepare booking data
    booking_dict = booking.model_dump()
    booking_dict['booking_type'] = 'custom'  # Force custom type
    booking_dict['booking_reference'] = generate_booking_reference()
    booking_dict['created_by'] = current_user.get('email') or current_user.get('username')
    
    # Add agency/branch info from current user
    if current_user.get('role') == 'agency':
        booking_dict['agency_id'] = str(current_user.get('_id'))
        booking_dict['agent_name'] = current_user.get('agency_name', 'Unknown')
    elif current_user.get('role') == 'branch':
        booking_dict['branch_id'] = str(current_user.get('_id'))
        booking_dict['agent_name'] = current_user.get('branch_name', 'Unknown')
    
    # Create booking in CUSTOM_BOOKINGS collection
    created_booking = await db_ops.create(Collections.CUSTOM_BOOKINGS, booking_dict)
    
    # Update package inventory - reduce available seats
    new_available_seats = available_seats - booking.total_passengers
    await db_ops.update(
        Collections.PACKAGES, 
        booking.ticket_id, 
        {"available_seats": new_available_seats}
    )
    
    return serialize_doc(created_booking)

@router.get("/", response_model=List[BookingResponse])
async def get_custom_bookings(
    booking_status: Optional[str] = None,
    payment_status: Optional[str] = None,
    booking_reference: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Get all custom package bookings with optional filtering"""
    filter_query = {}
    
    # Filter by agency/branch
    if current_user.get('role') == 'agency':
        filter_query['agency_id'] = str(current_user.get('_id'))
    elif current_user.get('role') == 'branch':
        filter_query['branch_id'] = str(current_user.get('_id'))
    
    if booking_status:
        filter_query['booking_status'] = booking_status
    if payment_status:
        filter_query['payment_status'] = payment_status
    if booking_reference:
        filter_query['booking_reference'] = {"$regex": booking_reference, "$options": "i"}
    
    bookings = await db_ops.get_all(Collections.CUSTOM_BOOKINGS, filter_query, skip=skip, limit=limit)
    return serialize_docs(bookings)

@router.get("/{booking_id}", response_model=BookingResponse)
async def get_custom_booking(
    booking_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get custom package booking by ID"""
    booking = await db_ops.get_by_id(Collections.CUSTOM_BOOKINGS, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Custom booking not found")
    
    # Check authorization
    if current_user.get('role') == 'agency' and booking.get('agency_id') != str(current_user.get('_id')):
        raise HTTPException(status_code=403, detail="Not authorized to view this booking")
    elif current_user.get('role') == 'branch' and booking.get('branch_id') != str(current_user.get('_id')):
        raise HTTPException(status_code=403, detail="Not authorized to view this booking")
    
    return serialize_doc(booking)

@router.put("/{booking_id}", response_model=BookingResponse)
async def update_custom_booking(
    booking_id: str,
    booking_update: BookingUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update custom package booking details"""
    update_data = booking_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    # Get existing booking
    booking = await db_ops.get_by_id(Collections.CUSTOM_BOOKINGS, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Custom booking not found")
    
    # Check authorization
    if current_user.get('role') == 'agency' and booking.get('agency_id') != str(current_user.get('_id')):
        raise HTTPException(status_code=403, detail="Not authorized to update this booking")
    elif current_user.get('role') == 'branch' and booking.get('branch_id') != str(current_user.get('_id')):
        raise HTTPException(status_code=403, detail="Not authorized to update this booking")
    
    updated_booking = await db_ops.update(Collections.CUSTOM_BOOKINGS, booking_id, update_data)
    if not updated_booking:
        raise HTTPException(status_code=404, detail="Custom booking not found")
    
    return serialize_doc(updated_booking)

@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_custom_booking(
    booking_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Cancel custom package booking and restore package inventory"""
    booking = await db_ops.get_by_id(Collections.CUSTOM_BOOKINGS, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Custom booking not found")
    
    # Check authorization
    if current_user.get('role') == 'agency' and booking.get('agency_id') != str(current_user.get('_id')):
        raise HTTPException(status_code=403, detail="Not authorized to cancel this booking")
    elif current_user.get('role') == 'branch' and booking.get('branch_id') != str(current_user.get('_id')):
        raise HTTPException(status_code=403, detail="Not authorized to cancel this booking")
    
    # Update booking status to cancelled
    await db_ops.update(Collections.CUSTOM_BOOKINGS, booking_id, {"booking_status": "cancelled"})
    
    # Restore package inventory
    package = await db_ops.get_by_id(Collections.PACKAGES, booking.get('ticket_id'))
    if package:
        current_available = package.get('available_seats', 0)
        restored_seats = current_available + booking.get('total_passengers', 0)
        await db_ops.update(
            Collections.PACKAGES,
            booking.get('ticket_id'),
            {"available_seats": restored_seats}
        )
