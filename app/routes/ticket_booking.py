"""
Ticket Booking routes - Dedicated API for flight ticket bookings
"""
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from typing import List, Optional, Any, Dict
from datetime import datetime
import random
import string
import shutil
import os
from pydantic import BaseModel, Field
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user
from app.finance.journal_engine import create_ticket_booking_journal
from bson import ObjectId

# ── Inline Pydantic models (booking.py was removed) ──────────────────────────

class TicketPassengerData(BaseModel):
    type: str = "Adult"
    title: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    passport: Optional[str] = Field(None, alias="passport_number")
    dob: Optional[str] = Field(None, alias="date_of_birth")
    passportIssue: Optional[str] = Field(None, alias="passport_issue_date")
    passportExpiry: Optional[str] = Field(None, alias="passport_expiry_date")
    country: Optional[str] = None
    
    class Config:
        populate_by_name = True
        extra = "allow"

class BookingCreate(BaseModel):
    ticket_id: str
    ticket_details: Optional[Dict[str, Any]] = Field(default={}, description="Complete ticket information")
    passengers: Optional[List[TicketPassengerData]] = []
    total_passengers: int = Field(default=1, ge=1)
    
    # Financial fields from frontend
    base_price_per_person: Optional[float] = 0
    tax_per_person: Optional[float] = 0
    service_charge_per_person: Optional[float] = 0
    subtotal: Optional[float] = 0
    total_tax: Optional[float] = 0
    total_service_charge: Optional[float] = 0
    grand_total: Optional[float] = 0
    
    # Discount fields
    discount_group_id: Optional[str] = None
    discount_amount: Optional[float] = 0
    
    # Backwards compatible financial fields
    total_amount: Optional[float] = 0
    
    payment_details: Optional[Dict[str, Any]] = Field(default_factory=dict)
    booking_status: Optional[str] = "underprocess"
    notes: Optional[str] = None
    agency_details: Optional[Dict[str, Any]] = None
    branch_details: Optional[Dict[str, Any]] = None
    organization_details: Optional[Dict[str, Any]] = None

class BookingUpdate(BaseModel):
    model_config = {"extra": "allow"}
    booking_status: Optional[str] = None
    payment_details: Optional[Dict[str, Any]] = None
    paid_amount: Optional[float] = None
    discount: Optional[float] = None
    child_price: Optional[float] = None
    infant_price: Optional[float] = None
    payment_details: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

class BookingResponse(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    booking_reference: Optional[str] = None
    booking_status: Optional[str] = None
    payment_status: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True
        extra = "allow"
        populate_by_name = True

router = APIRouter(prefix="/ticket-bookings", tags=["Ticket Bookings"])

def generate_booking_reference():
    """Generate unique booking reference like TB-YYMMDD-XXXX"""
    timestamp = datetime.now().strftime('%y%m%d')
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"TB-{timestamp}-{random_str}"

@router.post("/", status_code=status.HTTP_201_CREATED)
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
    booking_dict = booking.model_dump(mode='json', exclude_unset=False, exclude_none=False)
    print("DEBUG: Final booking dict payload being saved:", booking_dict)
    booking_dict['booking_type'] = 'ticket'  # Force ticket type
    booking_dict['booking_reference'] = generate_booking_reference()
    booking_dict['created_by'] = current_user.get('email') or current_user.get('username')
    booking_dict['created_at'] = datetime.utcnow().isoformat()
    # Set payment deadline (e.g., 3 hours from now)
    from datetime import timedelta
    booking_dict['payment_deadline'] = (datetime.utcnow() + timedelta(hours=3)).isoformat() + "Z"

    # ── resolve IDs from JWT (sub = entity _id; '_id' key is NOT in JWT payload) ──
    role      = current_user.get('role')
    agency_id = current_user.get('agency_id') or (current_user.get('sub') if role == 'agency' else None)
    branch_id = current_user.get('branch_id') or (current_user.get('sub') if role == 'branch' else None)
    org_id    = current_user.get('organization_id')

    booking_dict['agency_id']       = agency_id
    booking_dict['branch_id']       = branch_id
    booking_dict['organization_id'] = org_id
    booking_dict['agent_name']      = (
        current_user.get('agency_name') or
        current_user.get('branch_name') or
        current_user.get('email', 'Unknown')
    )

    # ── Record Booker Identity ──
    booking_dict['booked_by_role'] = role
    booking_dict['booked_by_id'] = current_user.get('sub')
    booking_dict['booked_by_name'] = (
        current_user.get('name') or 
        current_user.get('agency_name') or 
        current_user.get('branch_name') or 
        current_user.get('email', 'Unknown')
    )

    # ── If branch books directly, ensure agency_id is null ──
    if role == 'branch':
        booking_dict['agency_id'] = None

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
    
    # ── Auto-generate double-entry journal ──────────────────────────────────
    try:
        await create_ticket_booking_journal(
            booking=serialize_doc(created_booking),
            organization_id=org_id,
            branch_id=branch_id,
            agency_id=agency_id,
            created_by=booking_dict['created_by'],
        )
    except Exception as je:
        print(f"⚠️  Journal engine warning for {created_booking.get('booking_reference')}: {je}")
        
    # ── Auto-create pending payment for bank/cash ───────────────────────────
    pm_details = booking_dict.get("payment_details") or {}
    pmt_method = pm_details.get("payment_method")
    if pmt_method in ["bank_transfer", "bank", "cash", "bank transfer", "online", "transfer"]:
        payment_doc = {
            "booking_id": str(created_booking.get('_id')),
            "booking_type": "ticket",
            "payment_method": pmt_method,
            "amount": float(booking_dict.get('grand_total') or booking_dict.get('total_amount') or 0),
            "payment_date": booking_dict['created_at'],
            "status": "pending",
            "agency_id": agency_id,
            "branch_id": branch_id,
            "organization_id": org_id,
            "agent_name": booking_dict.get('agent_name'),
            "created_by": booking_dict['created_by'],
            "created_at": booking_dict['created_at'],
            "updated_at": booking_dict['created_at'],
            # Mirror transfer details to Payment record if present
            "transfer_account_number": pm_details.get("transfer_account_number"),
            "transfer_account_name": pm_details.get("transfer_account_name"),
            "transfer_phone": pm_details.get("transfer_phone"),
            "transfer_cnic": pm_details.get("transfer_cnic"),
            "transfer_account": pm_details.get("transfer_account")
        }
        await db_ops.create(Collections.PAYMENTS, payment_doc)

    # Update flight inventory - reduce available seats
    new_available_seats = available_seats - booking.total_passengers
    await db_ops.update(
        Collections.FLIGHTS, 
        booking.ticket_id, 
        {"available_seats": new_available_seats}
    )
    
    return serialize_doc(created_booking)

@router.get("/")
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
    role = current_user.get('role', '')
    entity_type = (current_user.get('entity_type') or '').lower()
    
    # Organization scoping: for admins, super_admins, and organization employees
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
    
    bookings = await db_ops.get_all(Collections.TICKET_BOOKINGS, filter_query, skip=skip, limit=limit)
    return serialize_docs(bookings)

@router.get("/{booking_id}")
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
    
    return serialize_doc(booking)

@router.put("/{booking_id}")
async def update_ticket_booking(
    booking_id: str,
    booking_update: BookingUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update ticket booking status/details — direct MongoDB update, no pre-GET needed."""
    from datetime import datetime

    update_data = booking_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    # Get existing booking
    booking = await db_ops.get_by_id(Collections.TICKET_BOOKINGS, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Ticket booking not found")
    
    # Check authorization
    if current_user.get('role') == 'agency':
        aid = current_user.get('agency_id') or current_user.get('sub')
        if booking.get('agency_id') != aid:
            raise HTTPException(status_code=403, detail="Not authorized to update this booking")
    elif current_user.get('role') == 'branch':
        bid = current_user.get('branch_id') or current_user.get('sub')
        if booking.get('branch_id') != bid:
            raise HTTPException(status_code=403, detail="Not authorized to update this booking")
    
    updated_booking = await db_ops.update(Collections.TICKET_BOOKINGS, booking_id, update_data)
    if not updated_booking:
        raise HTTPException(status_code=404, detail="Ticket booking not found")
    
    return serialize_doc(updated_booking)

    update_data["updated_at"] = datetime.utcnow()

    # Use the collection directly to avoid any db_ops wrapper issues
    try:
        oid = ObjectId(booking_id)
    except Exception as e:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid booking ID format or server error: {str(e)}"
        )

    from app.config.database import db_config as _db_config
    collection = _db_config.get_collection(Collections.TICKET_BOOKINGS)

    result = await collection.find_one_and_update(
        {"_id": oid},
        {"$set": update_data},
        return_document=True
    )

    if result is None:
        raise HTTPException(status_code=404, detail="Ticket booking not found in database")

    return serialize_doc(result)


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
    if current_user.get('role') == 'agency':
        aid = current_user.get('agency_id') or current_user.get('sub')
        if booking.get('agency_id') != aid:
            raise HTTPException(status_code=403, detail="Not authorized to cancel this booking")
    elif current_user.get('role') == 'branch':
        bid = current_user.get('branch_id') or current_user.get('sub')
        if booking.get('branch_id') != bid:
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
