"""
Booking routes
API endpoints for managing ticket/package bookings
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

router = APIRouter(prefix="/bookings", tags=["Bookings"])

def get_booking_collection(booking_type: str):
    """Helper to get the correct collection based on booking type"""
    collection_map = {
        "ticket": Collections.TICKET_BOOKINGS,
        "package": Collections.UMRAH_BOOKINGS,
        "custom": Collections.CUSTOM_BOOKINGS
    }
    return collection_map.get(booking_type, Collections.TICKET_BOOKINGS)

async def find_booking_in_all_collections(booking_id: str):
    """Search for a booking across all booking collections"""
    collections_to_search = [
        Collections.TICKET_BOOKINGS,
        Collections.UMRAH_BOOKINGS,
        Collections.CUSTOM_BOOKINGS
    ]
    
    for collection in collections_to_search:
        booking = await db_ops.get_by_id(collection, booking_id)
        if booking:
            return booking, collection
    return None, None

def generate_booking_reference():
    """Generate unique booking reference like BK-ABC123"""
    timestamp = datetime.now().strftime('%y%m%d')
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"BK-{timestamp}-{random_str}"

@router.post("/", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking(
    booking: BookingCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new booking and update ticket inventory"""
    
    # Determine collection based on booking type
    booking_collection = get_booking_collection(booking.booking_type)
    
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
    
    # Prepare booking data — use mode='json' to convert date/datetime to ISO strings (BSON-safe)
    booking_dict = booking.model_dump(mode='json')
    booking_dict['booking_reference'] = generate_booking_reference()
    booking_dict['created_by'] = current_user.get('email') or current_user.get('username')
    
    # Add agency/branch info from current user
    if current_user.get('role') == 'agency':
        aid = current_user.get('agency_id') or current_user.get('sub')
        booking_dict['agency_id'] = aid
        booking_dict['agent_name'] = current_user.get('agency_name', 'Unknown')
    elif current_user.get('role') == 'branch':
        bid = current_user.get('branch_id') or current_user.get('sub')
        booking_dict['branch_id'] = bid
        booking_dict['agent_name'] = current_user.get('branch_name', 'Unknown')
    
    # Create booking in appropriate collection
    created_booking = await db_ops.create(booking_collection, booking_dict)
    
    # Update ticket inventory - reduce available seats
    new_available_seats = available_seats - booking.total_passengers
    await db_ops.update(
        Collections.FLIGHTS, 
        booking.ticket_id, 
        {"available_seats": new_available_seats}
    )
    
    return serialize_doc(created_booking)

@router.get("/", response_model=List[BookingResponse])
async def get_bookings(
    booking_type: Optional[str] = None,
    booking_status: Optional[str] = None,
    payment_status: Optional[str] = None,
    booking_reference: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Get all bookings with optional filtering"""
    filter_query = {}
    
    role = current_user.get('role', '')
    entity_type = (current_user.get('entity_type') or '').lower()

    # Filter by agency/branch/org
    if role in ('organization', 'org', 'admin', 'super_admin') or entity_type in ('organization', 'org'):
        # Org users see all bookings under their org EXCLUDING those made by child branches/agencies
        oid = current_user.get('organization_id') or current_user.get('sub')
        if oid:
            filter_query['organization_id'] = oid
            # Ensure it's an organization-level booking (not branch or agency)
            filter_query['branch_id'] = None
            filter_query['agency_id'] = None
    elif role == 'agency' or entity_type == 'agency':
        aid = current_user.get('agency_id') or current_user.get('entity_id') or current_user.get('sub')
        filter_query['agency_id'] = aid
    elif role == 'branch' or entity_type == 'branch':
        bid = current_user.get('branch_id') or current_user.get('entity_id') or current_user.get('sub')
        filter_query['branch_id'] = bid
        # Only show bookings made directly by the branch
        filter_query['booked_by_role'] = 'branch'
    
    if booking_status:
        filter_query['booking_status'] = booking_status
    if payment_status:
        filter_query['payment_status'] = payment_status
    if booking_reference:
        filter_query['booking_reference'] = {"$regex": booking_reference, "$options": "i"}
    
    # Determine which collection(s) to query
    if booking_type:
        collection = get_booking_collection(booking_type)
        bookings = await db_ops.get_all(collection, filter_query, skip=skip, limit=limit)
    else:
        # Search all booking collections
        all_bookings = []
        for coll in [Collections.TICKET_BOOKINGS, Collections.UMRAH_BOOKINGS, Collections.CUSTOM_BOOKINGS]:
            bookings = await db_ops.get_all(coll, filter_query, skip=skip, limit=limit)
            all_bookings.extend(bookings)
        bookings = all_bookings[:limit]
    
    return serialize_docs(bookings)

@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get booking by ID"""
    booking, collection = await find_booking_in_all_collections(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Check authorization
    if current_user.get('role') == 'agency':
        aid = current_user.get('agency_id') or current_user.get('sub')
        if booking.get('agency_id') != aid:
            raise HTTPException(status_code=403, detail="Not authorized to view this booking")
    elif current_user.get('role') == 'branch':
        bid = current_user.get('branch_id') or current_user.get('sub')
        if booking.get('branch_id') != bid:
            raise HTTPException(status_code=403, detail="Not authorized to view this booking")
    
    return serialize_doc(booking)

@router.put("/{booking_id}", response_model=BookingResponse)
async def update_booking(
    booking_id: str,
    booking_update: BookingUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update booking details (payment status, booking status, etc.)"""
    update_data = booking_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    # Get existing booking
    booking, collection = await find_booking_in_all_collections(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Check authorization
    if current_user.get('role') == 'agency':
        aid = current_user.get('agency_id') or current_user.get('sub')
        if booking.get('agency_id') != aid:
            raise HTTPException(status_code=403, detail="Not authorized to update this booking")
    elif current_user.get('role') == 'branch':
        bid = current_user.get('branch_id') or current_user.get('sub')
        if booking.get('branch_id') != bid:
            raise HTTPException(status_code=403, detail="Not authorized to update this booking")
    
    updated_booking = await db_ops.update(collection, booking_id, update_data)
    if not updated_booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    return serialize_doc(updated_booking)

@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_booking(
    booking_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Cancel booking and restore ticket inventory"""
    booking, collection = await find_booking_in_all_collections(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Check authorization
    if current_user.get('role') == 'agency':
        aid = current_user.get('agency_id') or current_user.get('sub')
        if booking.get('agency_id') != aid:
            raise HTTPException(status_code=403, detail="Not authorized to cancel this booking")
    elif current_user.get('role') == 'branch':
        bid = current_user.get('branch_id') or current_user.get('sub')
        if booking.get('branch_id') != bid:
            raise HTTPException(status_code=403, detail="Not authorized to cancel this booking")
    
    # Update booking status to cancelled
    await db_ops.update(collection, booking_id, {"booking_status": "cancelled"})
    
    # Restore ticket inventory
    ticket = await db_ops.get_by_id(Collections.FLIGHTS, booking.get('ticket_id'))
    if ticket:
        current_available = ticket.get('available_seats', 0)
        restored_seats = current_available + booking.get('total_passengers', 0)
        await db_ops.update(
            Collections.FLIGHTS, 
            booking.get('ticket_id'), 
            {"available_seats": restored_seats}
        )
