"""
Umrah Package Booking routes - Dedicated API for Umrah package bookings
"""
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from typing import List, Optional, Dict, Any
from datetime import datetime
import random, string, os, shutil, uuid
from pydantic import BaseModel

from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user
from app.finance.journal_engine import create_umrah_booking_journal

router = APIRouter(prefix="/umrah-bookings", tags=["Umrah Bookings"])

# ── Pydantic models (self-contained so booking.py is not required) ──────────

class PassengerData(BaseModel):
    type: str  # adult | child | infant
    room_type: Optional[str] = None
    room_index: Optional[int] = None
    slot_in_room: Optional[int] = None
    name: str
    title: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    passport_no: str
    passport_issue: Optional[str] = None    # YYYY-MM-DD
    passport_expiry: Optional[str] = None   # YYYY-MM-DD
    dob: Optional[str] = None               # YYYY-MM-DD
    country: Optional[str] = None
    gender: Optional[str] = None
    nationality: Optional[str] = "Pakistani"
    passport_path: Optional[str] = None     # server file path after upload
    # ── family fields (auto-computed: first adult per room = family head) ──
    family_id: Optional[str] = None         # e.g. 'double_1', 'sharing_2'
    family_label: Optional[str] = None      # e.g. 'Double Room 1'
    is_family_head: Optional[bool] = False
    family_head_name: Optional[str] = None
    family_head_passport: Optional[str] = None

class RoomSelection(BaseModel):
    room_type: str   # sharing|quint|quad|triple|double
    quantity: int
    price_per_person: float

class UmrahBookingCreate(BaseModel):
    package_id: str
    package_details: Optional[Dict[str, Any]] = None   # full package object (includes flight, hotels, transport, prices)
    rooms_selected: List[RoomSelection] = []
    passengers: List[PassengerData] = []
    total_passengers: int = 0
    total_amount: float = 0
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    payment_details: Optional[Dict[str, Any]] = None
    booking_status: str = "underprocess"
    notes: Optional[str] = None
    # Hierarchy snapshots (populated server-side, ignored if sent by client)
    agency_details: Optional[Dict[str, Any]] = None
    branch_details: Optional[Dict[str, Any]] = None
    organization_details: Optional[Dict[str, Any]] = None

class UmrahBookingUpdate(BaseModel):
    booking_status: Optional[str] = None
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    payment_details: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

PASSPORT_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "passports")
os.makedirs(PASSPORT_UPLOAD_DIR, exist_ok=True)

def generate_booking_reference():
    timestamp = datetime.now().strftime('%y%m%d')
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"UB-{timestamp}-{random_str}"

# ── Passport upload ──────────────────────────────────────────────────────────

@router.post("/upload-passport")
async def upload_passport_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload a passenger passport image; returns the stored file path."""
    allowed = {"image/jpeg", "image/png", "image/jpg", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG/PNG images allowed")
    ext = os.path.splitext(file.filename or "passport.jpg")[1] or ".jpg"
    unique_name = f"passport_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{random.randint(1000,9999)}{ext}"
    dest = os.path.join(PASSPORT_UPLOAD_DIR, unique_name)
    with open(dest, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"path": f"/uploads/passports/{unique_name}", "filename": unique_name}

# ── CRUD ─────────────────────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_umrah_booking(
    booking: UmrahBookingCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new Umrah package booking"""
    package = await db_ops.get_by_id(Collections.PACKAGES, booking.package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    booking_dict = booking.model_dump()
    booking_dict['booking_type'] = 'umrah_package'
    booking_dict['booking_reference'] = generate_booking_reference()
    booking_dict['created_by'] = current_user.get('email') or current_user.get('username')
    booking_dict['created_at'] = datetime.utcnow().isoformat()

    # ── resolve IDs from JWT (sub = entity's _id; _id key is NOT in payload) ──
    role = current_user.get('role')
    agency_id = current_user.get('agency_id')  or (current_user.get('sub') if role == 'agency' else None)
    branch_id = current_user.get('branch_id')  or (current_user.get('sub') if role == 'branch' else None)
    org_id    = current_user.get('organization_id')

    booking_dict['agency_id']       = agency_id
    booking_dict['branch_id']       = branch_id
    booking_dict['organization_id'] = org_id
    booking_dict['agent_name']      = (
        current_user.get('agency_name') or
        current_user.get('branch_name') or
        current_user.get('email', 'Unknown')
    )

    # ── fetch & embed full hierarchy documents (strip password fields) ──
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

    created_booking = await db_ops.create(Collections.UMRAH_BOOKINGS, booking_dict)
    created = serialize_doc(created_booking)

    # ── Auto-generate double-entry journal ──────────────────────────────────
    try:
        await create_umrah_booking_journal(
            booking=created,
            organization_id=org_id,
            branch_id=branch_id,
            agency_id=agency_id,
            created_by=booking_dict['created_by'],
        )
    except Exception as je:
        # Journal failure must NOT block the booking – log and continue
        print(f"⚠️  Journal engine warning for {created.get('booking_reference')}: {je}")

    return created

@router.get("/")
async def get_umrah_bookings(
    booking_status: Optional[str] = None,
    payment_status: Optional[str] = None,
    booking_reference: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    filter_query = {}
    if current_user.get('role') == 'agency':
        aid = current_user.get('agency_id') or current_user.get('sub')
        filter_query['agency_id'] = aid
    elif current_user.get('role') == 'branch':
        bid = current_user.get('branch_id') or current_user.get('sub')
        filter_query['branch_id'] = bid
    if booking_status:
        filter_query['booking_status'] = booking_status
    if payment_status:
        filter_query['payment_status'] = payment_status
    if booking_reference:
        filter_query['booking_reference'] = {"$regex": booking_reference, "$options": "i"}
    bookings = await db_ops.get_all(Collections.UMRAH_BOOKINGS, filter_query, skip=skip, limit=limit)
    return serialize_docs(bookings)

@router.get("/{booking_id}")
async def get_umrah_booking(booking_id: str, current_user: dict = Depends(get_current_user)):
    booking = await db_ops.get_by_id(Collections.UMRAH_BOOKINGS, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Umrah booking not found")
    return serialize_doc(booking)

@router.put("/{booking_id}")
async def update_umrah_booking(
    booking_id: str,
    booking_update: UmrahBookingUpdate,
    current_user: dict = Depends(get_current_user)
):
    update_data = booking_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    booking = await db_ops.get_by_id(Collections.UMRAH_BOOKINGS, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Umrah booking not found")
    updated_booking = await db_ops.update(Collections.UMRAH_BOOKINGS, booking_id, update_data)
    return serialize_doc(updated_booking)

@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_umrah_booking(booking_id: str, current_user: dict = Depends(get_current_user)):
    booking = await db_ops.get_by_id(Collections.UMRAH_BOOKINGS, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Umrah booking not found")
    await db_ops.update(Collections.UMRAH_BOOKINGS, booking_id, {"booking_status": "cancelled"})
