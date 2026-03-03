"""
Ticket Booking routes - Dedicated API for flight ticket bookings
"""
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from typing import List, Optional, Any, Dict
from datetime import datetime, timedelta
import random
import string
import shutil
import os
from pydantic import BaseModel, Field
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user

# ── Inline Pydantic models (booking.py was removed) ──────────────────────────

class TicketPassengerData(BaseModel):
    type: str = "Adult"
    name: Optional[str] = None
    title: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    passport_no: Optional[str] = None
    passport_issue: Optional[str] = None
    passport_expiry: Optional[str] = None
    dob: Optional[str] = None
    country: Optional[str] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    passport_path: Optional[str] = None

class BookingCreate(BaseModel):
    ticket_id: str
    ticket_details: Optional[Dict[str, Any]] = None  # Full ticket snapshot from frontend (will be overwritten by DB fetch)
    passengers: Optional[List[TicketPassengerData]] = []
    total_passengers: int = Field(default=1, ge=1)
    # Financial fields
    base_price_per_person: Optional[float] = 0
    tax_per_person: Optional[float] = 0
    service_charge_per_person: Optional[float] = 0
    subtotal: Optional[float] = 0
    total_tax: Optional[float] = 0
    total_service_charge: Optional[float] = 0
    grand_total: Optional[float] = 0
    total_amount: Optional[float] = 0
    discount_group_id: Optional[str] = None
    discount_amount: Optional[float] = 0
    paid_amount: Optional[float] = 0
    # Payment
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    payment_details: Optional[Dict[str, Any]] = {}
    # Status
    booking_status: Optional[str] = "underprocess"
    order_status: Optional[str] = "underprocess"
    voucher_status: Optional[str] = "Draft"
    notes: Optional[str] = None
    # Agency/Branch/Org — optional, backend will re-derive from JWT
    agency_details: Optional[Dict[str, Any]] = None
    branch_details: Optional[Dict[str, Any]] = None
    organization_details: Optional[Dict[str, Any]] = None

class BookingUpdate(BaseModel):
    booking_status: Optional[str] = None
    order_status: Optional[str] = None
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    paid_amount: Optional[float] = None
    payment_details: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    voucher_status: Optional[str] = None
    discount: Optional[float] = None
    discount_amount: Optional[float] = None
    infant_price: Optional[float] = None
    child_price: Optional[float] = None
    pnr: Optional[str] = None

class BookingResponse(BaseModel):
    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}

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
    now_utc = datetime.utcnow()
    booking_dict['created_at'] = now_utc.isoformat()
    booking_dict['payment_deadline'] = (now_utc + timedelta(hours=24)).isoformat()

    # ── Embed full ticket details snapshot into the booking ──
    ticket_snapshot = serialize_doc(ticket)
    ticket_snapshot.pop('password', None)
    booking_dict['ticket_details'] = ticket_snapshot

    # ── Sync total_amount = grand_total if not separately provided ──
    if not booking_dict.get('total_amount') and booking_dict.get('grand_total'):
        booking_dict['total_amount'] = booking_dict['grand_total']

    # ── resolve IDs from JWT (sub = entity _id; '_id' key is NOT in JWT payload) ──
    role      = current_user.get('role')
    agency_id = current_user.get('agency_id') or (current_user.get('sub') if role == 'agency' else None)
    branch_id = (
        current_user.get('branch_id') or
        (current_user.get('sub') if role == 'branch' else None) or
        (current_user.get('entity_id') if current_user.get('entity_type') == 'branch' else None)
    )
    org_id    = current_user.get('organization_id')

    booking_dict['agency_id']       = agency_id
    booking_dict['branch_id']       = branch_id
    booking_dict['organization_id'] = org_id
    booking_dict['agent_name']      = (
        current_user.get('agency_name') or
        current_user.get('branch_name') or
        current_user.get('email', 'Unknown')
    )

    # ── fetch & embed full hierarchy documents (strip passwords) ──
    if agency_id:
        agency_doc = await db_ops.get_by_id(Collections.AGENCIES, agency_id)
        if agency_doc:
            ad = serialize_doc(agency_doc)
            ad.pop('password', None); ad.pop('hashed_password', None)
            booking_dict['agency_details'] = ad

    if branch_id:
        branch_doc = await db_ops.get_by_id(Collections.BRANCHES, branch_id)
        if branch_doc:
            bd = serialize_doc(branch_doc)
            bd.pop('password', None); bd.pop('hashed_password', None)
            booking_dict['branch_details'] = bd

    if org_id:
        org_doc = await db_ops.get_by_id(Collections.ORGANIZATIONS, org_id)
        if org_doc:
            booking_dict['organization_details'] = serialize_doc(org_doc)
    
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

async def _populate_ticket_details(booking: dict) -> dict:
    """If ticket_details is missing, fetch from ticket inventory and embed."""
    if not booking.get('ticket_details') and booking.get('ticket_id'):
        ticket = await db_ops.get_by_id(Collections.FLIGHTS, booking['ticket_id'])
        if ticket:
            snapshot = serialize_doc(ticket)
            snapshot.pop('password', None)
            booking['ticket_details'] = snapshot
            await db_ops.update(
                Collections.TICKET_BOOKINGS,
                str(booking.get('_id', '')),
                {'ticket_details': snapshot}
            )
    return booking

async def _ensure_payment_deadline(booking: dict, collection) -> dict:
    """If payment_deadline is missing, derive it from created_at + 24h and persist."""
    if not booking.get('payment_deadline') and booking.get('created_at'):
        try:
            deadline = (datetime.fromisoformat(booking['created_at']) + timedelta(hours=24)).isoformat()
        except Exception:
            deadline = (datetime.utcnow() + timedelta(hours=24)).isoformat()
        booking['payment_deadline'] = deadline
        await db_ops.update(collection, str(booking.get('_id', '')), {'payment_deadline': deadline})
    return booking

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
    role = current_user.get('role')
    entity_type = current_user.get('entity_type')
    entity_id = current_user.get('entity_id')

    if role == 'agency' or entity_type == 'agency':
        aid = current_user.get('agency_id') or entity_id or current_user.get('sub')
        filter_query['agency_id'] = aid
        # Restrict to only bookings created by this user/email
        if current_user.get('email'):
            filter_query['created_by'] = current_user.get('email')
    elif role == 'branch' or entity_type == 'branch':
        bid = current_user.get('branch_id') or entity_id or current_user.get('sub')
        filter_query['branch_id'] = bid
        # Restrict to only bookings created by this user/email
        if current_user.get('email'):
            filter_query['created_by'] = current_user.get('email')
    
    if booking_status:
        filter_query['booking_status'] = booking_status
    if payment_status:
        filter_query['payment_status'] = payment_status
    if booking_reference:
        filter_query['booking_reference'] = {"$regex": booking_reference, "$options": "i"}
    
    bookings = await db_ops.get_all(Collections.TICKET_BOOKINGS, filter_query, skip=skip, limit=limit)
    enriched = []
    for b in bookings:
        b = await _populate_ticket_details(b)
        b = await _ensure_payment_deadline(b, Collections.TICKET_BOOKINGS)
        enriched.append(b)
    return serialize_docs(enriched)

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
    if current_user.get('role') == 'agency':
        aid = current_user.get('agency_id') or current_user.get('sub')
        if booking.get('agency_id') != aid:
            raise HTTPException(status_code=403, detail="Not authorized to view this booking")
    elif current_user.get('role') == 'branch':
        bid = current_user.get('branch_id') or current_user.get('sub')
        if booking.get('branch_id') != bid:
            raise HTTPException(status_code=403, detail="Not authorized to view this booking")
    
    booking = await _populate_ticket_details(booking)
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

    # Sync discount → discount_amount
    if 'discount' in update_data and 'discount_amount' not in update_data:
        update_data['discount_amount'] = update_data.pop('discount')
    elif 'discount' in update_data:
        update_data.pop('discount')

    update_data['updated_at'] = datetime.utcnow().isoformat()
    
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