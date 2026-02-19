"""
Ticket Booking routes - Dedicated API for flight ticket bookings
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

router = APIRouter(prefix="/ticket-bookings", tags=["Ticket Bookings"])

def generate_booking_reference():
    """Generate unique booking reference like TB-YYMMDD-XXXX"""
    timestamp = datetime.now().strftime('%y%m%d')
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"TB-{timestamp}-{random_str}"

@router.post("/", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket_booking(
    booking: BookingCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new ticket booking and update flight inventory"""
    
    # Verify ticket exists and has enough seats
    ticket = await db_ops.get_by_id(Collections.FLIGHTS, booking.ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    if not ticket.get('is_active', False):
        raise HTTPException(status_code=400, detail="Ticket is not active")
    
    available_seats = ticket.get('available_seats', 0)
    if available_seats < booking.total_passengers:
        raise HTTPException(
            status_code=400, 
            detail=f"Not enough seats available. Only {available_seats} seats left."
        )
    
    # Prepare booking data
    booking_dict = booking.model_dump()
    booking_dict['booking_type'] = 'ticket'  # Force ticket type
    booking_dict['booking_reference'] = generate_booking_reference()
    booking_dict['created_by'] = current_user.get('email') or current_user.get('username')
    
    # Add agency/branch info from current user
    if current_user.get('role') == 'agency':
        booking_dict['agency_id'] = str(current_user.get('_id'))
        booking_dict['agent_name'] = current_user.get('agency_name', 'Unknown')
    elif current_user.get('role') == 'branch':
        booking_dict['branch_id'] = str(current_user.get('_id'))
        booking_dict['agent_name'] = current_user.get('branch_name', 'Unknown')
    
    # Create booking in TICKET_BOOKINGS collection
    created_booking = await db_ops.create(Collections.TICKET_BOOKINGS, booking_dict)
    
    # Update flight inventory - reduce available seats
    new_available_seats = available_seats - booking.total_passengers
    await db_ops.update(
        Collections.FLIGHTS, 
        booking.ticket_id, 
        {"available_seats": new_available_seats}
    )
    
    return serialize_doc(created_booking)

@router.get("/", response_model=List[BookingResponse])
async def get_ticket_bookings(
    booking_status: Optional[str] = None,
    payment_status: Optional[str] = None,
    booking_reference: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Get all ticket bookings with optional filtering"""
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
    
    bookings = await db_ops.get_all(Collections.TICKET_BOOKINGS, filter_query, skip=skip, limit=limit)
    return serialize_docs(bookings)

@router.get("/{booking_id}", response_model=BookingResponse)
async def get_ticket_booking(
    booking_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get ticket booking by ID"""
    booking = await db_ops.get_by_id(Collections.TICKET_BOOKINGS, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Ticket booking not found")
    
    # Check authorization
    if current_user.get('role') == 'agency' and booking.get('agency_id') != str(current_user.get('_id')):
        raise HTTPException(status_code=403, detail="Not authorized to view this booking")
    elif current_user.get('role') == 'branch' and booking.get('branch_id') != str(current_user.get('_id')):
        raise HTTPException(status_code=403, detail="Not authorized to view this booking")
    
    return serialize_doc(booking)

@router.put("/{booking_id}", response_model=BookingResponse)
async def update_ticket_booking(
    booking_id: str,
    booking_update: BookingUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update ticket booking details"""
    update_data = booking_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    # Get existing booking
    booking = await db_ops.get_by_id(Collections.TICKET_BOOKINGS, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Ticket booking not found")
    
    # Check authorization
    if current_user.get('role') == 'agency' and booking.get('agency_id') != str(current_user.get('_id')):
        raise HTTPException(status_code=403, detail="Not authorized to update this booking")
    elif current_user.get('role') == 'branch' and booking.get('branch_id') != str(current_user.get('_id')):
        raise HTTPException(status_code=403, detail="Not authorized to update this booking")
    
    updated_booking = await db_ops.update(Collections.TICKET_BOOKINGS, booking_id, update_data)
    if not updated_booking:
        raise HTTPException(status_code=404, detail="Ticket booking not found")
    
    return serialize_doc(updated_booking)

@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_ticket_booking(
    booking_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Cancel ticket booking and restore flight inventory"""
    booking = await db_ops.get_by_id(Collections.TICKET_BOOKINGS, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Ticket booking not found")
    
    # Check authorization
    if current_user.get('role') == 'agency' and booking.get('agency_id') != str(current_user.get('_id')):
        raise HTTPException(status_code=403, detail="Not authorized to cancel this booking")
    elif current_user.get('role') == 'branch' and booking.get('branch_id') != str(current_user.get('_id')):
        raise HTTPException(status_code=403, detail="Not authorized to cancel this booking")
    
    # Update booking status to cancelled
    await db_ops.update(Collections.TICKET_BOOKINGS, booking_id, {"booking_status": "cancelled"})
    
    # Restore flight inventory
    ticket = await db_ops.get_by_id(Collections.FLIGHTS, booking.get('ticket_id'))
    if ticket:
        current_available = ticket.get('available_seats', 0)
        restored_seats = current_available + booking.get('total_passengers', 0)
        await db_ops.update(
            Collections.FLIGHTS,
            booking.get('ticket_id'),
            {"available_seats": restored_seats}
        )
