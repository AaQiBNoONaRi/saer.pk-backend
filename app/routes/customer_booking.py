"""
Customer Booking Routes — Public website bookings (no login required)
Saved to 'customer_bookings' collection, visible in org portal Order Delivery → Customer Orders tab.
"""
import random
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from pydantic import BaseModel

from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user

import os, shutil

PASSPORT_UPLOAD_DIR = os.path.join("uploads", "passports")
os.makedirs(PASSPORT_UPLOAD_DIR, exist_ok=True)

router = APIRouter(prefix="/customer-bookings", tags=["Customer Bookings"])


# ─── Pydantic Models ──────────────────────────────────────────────────────────

class PassengerIn(BaseModel):
    type: str                           # adult / child / infant
    title: Optional[str] = None         # MR / MRS / MS / MSTR / MISS
    first_name: str
    last_name: str
    passport_no: Optional[str] = None
    passport_issue: Optional[str] = None
    passport_expiry: Optional[str] = None
    dob: Optional[str] = None
    country: Optional[str] = None
    passport_path: Optional[str] = None  # uploaded file path

class CustomerBookingCreate(BaseModel):
    package_id: str
    package_details: Optional[Dict[str, Any]] = None   # full package snapshot
    contact_name: str
    contact_phone: str
    contact_email: Optional[str] = None
    passengers: List[PassengerIn]
    room_type: Optional[str] = "sharing"               # sharing / double / triple / quad / quint
    total_passengers: int
    adults: int = 0
    children: int = 0
    infants: int = 0
    total_amount: float = 0
    payment_method: Optional[str] = None               # bank_transfer / jazzcash / easypaisa
    payment_status: Optional[str] = "unpaid"
    notes: Optional[str] = None

class CustomerBookingUpdate(BaseModel):
    booking_status: Optional[str] = None
    payment_status: Optional[str] = None
    order_status: Optional[str] = None
    notes: Optional[str] = None
    rejection_reason: Optional[str] = None


# ─── Helpers ─────────────────────────────────────────────────────────────────

def generate_booking_reference():
    ts = datetime.now().strftime('%y%m%d')
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"CB-{ts}-{rand}"


# ─── Public: Get bank accounts for payment instructions ──────────────────────

@router.get("/payment-info/banks")
async def get_payment_bank_accounts():
    """Public: fetch org bank accounts to show payment instructions."""
    accounts = await db_ops.get_all(Collections.BANK_ACCOUNTS, {}, skip=0, limit=20)
    safe = []
    for a in accounts:
        s = serialize_doc(a)
        # Only expose necessary field (no sensitive internal fields)
        safe.append({
            'bank_name':     s.get('bank_name', ''),
            'account_title': s.get('account_title', ''),
            'account_number': s.get('account_number', ''),
            'iban':          s.get('iban', ''),
            'account_type':  s.get('account_type', ''),
        })
    return safe


# ─── Passport Upload ──────────────────────────────────────────────────────────

@router.post("/upload-passport")
async def upload_passport(file: UploadFile = File(...)):
    """Upload a passport image — no auth required for public website."""
    allowed = {"image/jpeg", "image/png", "image/jpg", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG/PNG images allowed")
    ext = os.path.splitext(file.filename or "passport.jpg")[1] or ".jpg"
    name = f"passport_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{random.randint(1000,9999)}{ext}"
    dest = os.path.join(PASSPORT_UPLOAD_DIR, name)
    with open(dest, "wb") as buf:
        shutil.copyfileobj(file.file, buf)
    return {"path": f"/uploads/passports/{name}", "filename": name}


# ─── Public: Create Booking ───────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_customer_booking(booking: CustomerBookingCreate):
    """
    Create a customer booking from the public website.
    No authentication required.
    """
    # Verify package exists
    package = await db_ops.get_by_id(Collections.PACKAGES, booking.package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    booking_dict = booking.model_dump()
    booking_dict['booking_type']      = 'umrah_package'
    booking_dict['source']            = 'customer'          # key for org portal classification
    booking_dict['booking_reference'] = generate_booking_reference()
    booking_dict['booking_status']    = 'underprocess'
    booking_dict['order_status']      = 'underprocess'

    now_utc = datetime.utcnow()
    booking_dict['created_at']      = now_utc.isoformat()
    booking_dict['updated_at']      = now_utc.isoformat()

    # Embed full package snapshot if not already provided
    if not booking_dict.get('package_details'):
        from app.utils.helpers import serialize_doc as sd
        booking_dict['package_details'] = sd(package)

    # No agency/branch — these are null for customer bookings
    booking_dict['agency_id']       = None
    booking_dict['branch_id']       = None
    booking_dict['organization_id'] = None

    created = await db_ops.create(Collections.CUSTOMER_BOOKINGS, booking_dict)
    return serialize_doc(created)


# ─── Public: Track a single booking by ID ────────────────────────────────────

@router.get("/track/{booking_id}")
async def track_customer_booking(booking_id: str):
    """Public endpoint: customer can check their booking status."""
    booking = await db_ops.get_by_id(Collections.CUSTOMER_BOOKINGS, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return serialize_doc(booking)


# ─── Authenticated: list all customer bookings (org staff) ───────────────────

@router.get("/")
async def list_customer_bookings(
    booking_status: Optional[str] = None,
    skip: int = 0,
    limit: int = 200,
    current_user: dict = Depends(get_current_user)
):
    """Org/admin staff: get all customer bookings."""
    fq = {"source": "customer"}
    if booking_status:
        fq["booking_status"] = booking_status

    bookings = await db_ops.get_all(Collections.CUSTOMER_BOOKINGS, fq, skip=skip, limit=limit)
    return serialize_docs(bookings)


# ─── Authenticated: get single booking ───────────────────────────────────────

@router.get("/{booking_id}")
async def get_customer_booking(
    booking_id: str,
    current_user: dict = Depends(get_current_user)
):
    booking = await db_ops.get_by_id(Collections.CUSTOMER_BOOKINGS, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return serialize_doc(booking)


# ─── Authenticated: update booking status (approve / cancel / reject) ─────────

@router.put("/{booking_id}")
async def update_customer_booking(
    booking_id: str,
    data: CustomerBookingUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Org staff: approve, cancel, reject a customer booking."""
    booking = await db_ops.get_by_id(Collections.CUSTOMER_BOOKINGS, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    update = data.model_dump(exclude_none=True)
    update['updated_at'] = datetime.utcnow().isoformat()
    update['updated_by'] = current_user.get('email') or current_user.get('username')

    updated = await db_ops.update(Collections.CUSTOMER_BOOKINGS, booking_id, update)
    return serialize_doc(updated)
