"""
Custom Package Booking routes - self-contained, no BookingCreate model dependency
"""
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from typing import List, Optional, Dict, Any
from datetime import datetime
import random, string, os, shutil
from pydantic import BaseModel

from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user

router = APIRouter(prefix="/custom-bookings", tags=["Custom Bookings"])

# ── Pydantic models ──────────────────────────────────────────────────────────

class CustomPassengerData(BaseModel):
    type: str                                    # adult | child | infant
    name: str
    title: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    passport_no: str
    passport_issue: Optional[str] = None
    passport_expiry: Optional[str] = None
    dob: Optional[str] = None
    country: Optional[str] = None
    gender: Optional[str] = None
    nationality: Optional[str] = "Pakistani"
    passport_path: Optional[str] = None
    family_id: Optional[str] = None
    family_label: Optional[str] = None
    is_family_head: Optional[bool] = False
    family_head_name: Optional[str] = None
    family_head_passport: Optional[str] = None

class CustomRoomSelection(BaseModel):
    family_id: Optional[str] = None
    hotel_id: Optional[str] = None
    hotel_name: Optional[str] = None
    city: Optional[str] = None
    room_type: str
    quantity: int
    nights: Optional[int] = 0
    rate_sar: Optional[float] = 0
    rate_pkr: Optional[float] = 0

class CustomBookingCreate(BaseModel):
    package_details: Optional[Dict[str, Any]] = None   # full calculator state snapshot
    rooms_selected: List[CustomRoomSelection] = []
    passengers: List[CustomPassengerData] = []
    total_passengers: int = 0
    total_amount: float = 0
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    payment_details: Optional[Dict[str, Any]] = None
    booking_status: str = "underprocess"
    notes: Optional[str] = None
    agency_details: Optional[Dict[str, Any]] = None
    branch_details: Optional[Dict[str, Any]] = None
    organization_details: Optional[Dict[str, Any]] = None

class CustomBookingUpdate(BaseModel):
    booking_status: Optional[str] = None
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    payment_details: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

PASSPORT_UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "uploads", "passports"
)
os.makedirs(PASSPORT_UPLOAD_DIR, exist_ok=True)

def generate_booking_reference():
    timestamp = datetime.now().strftime('%y%m%d')
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"CB-{timestamp}-{rand}"

# ── Passport upload ──────────────────────────────────────────────────────────

@router.post("/upload-passport")
async def upload_passport(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    allowed = {"image/jpeg", "image/png", "image/jpg", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG/PNG images allowed")
    ext = os.path.splitext(file.filename or "passport.jpg")[1] or ".jpg"
    name = f"passport_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{random.randint(1000,9999)}{ext}"
    dest = os.path.join(PASSPORT_UPLOAD_DIR, name)
    with open(dest, "wb") as buf:
        shutil.copyfileobj(file.file, buf)
    return {"path": f"/uploads/passports/{name}", "filename": name}

# ── CRUD ─────────────────────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_custom_booking(
    booking: CustomBookingCreate,
    current_user: dict = Depends(get_current_user)
):
    booking_dict = booking.model_dump()
    booking_dict['booking_type']      = 'custom'
    booking_dict['booking_reference'] = generate_booking_reference()
    booking_dict['created_by']        = current_user.get('email') or current_user.get('username')
    booking_dict['created_at']        = datetime.utcnow().isoformat()

    # ── resolve IDs from JWT ──
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

    # ── fetch & embed full hierarchy documents ──
    if agency_id:
        doc = await db_ops.get_by_id(Collections.AGENCIES, agency_id)
        if doc:
            ad = serialize_doc(doc)
            ad.pop('password', None); ad.pop('hashed_password', None)
            booking_dict['agency_details'] = ad

    if branch_id:
        doc = await db_ops.get_by_id(Collections.BRANCHES, branch_id)
        if doc:
            bd = serialize_doc(doc)
            bd.pop('password', None); bd.pop('hashed_password', None)
            booking_dict['branch_details'] = bd

    if org_id:
        doc = await db_ops.get_by_id(Collections.ORGANIZATIONS, org_id)
        if doc:
            booking_dict['organization_details'] = serialize_doc(doc)

    created = await db_ops.create(Collections.CUSTOM_BOOKINGS, booking_dict)
    return serialize_doc(created)


@router.get("/")
async def get_custom_bookings(
    booking_status: Optional[str] = None,
    payment_status: Optional[str] = None,
    booking_reference: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    filter_query = {}
    
    role = current_user.get('role')
    entity_type = current_user.get('entity_type')
    
    if role == 'agency' or entity_type == 'agency':
        aid = current_user.get('agency_id') or current_user.get('entity_id') or current_user.get('sub')
        filter_query['agency_id'] = aid
    elif role == 'branch' or entity_type == 'branch':
        bid = current_user.get('branch_id') or current_user.get('entity_id') or current_user.get('sub')
        filter_query['branch_id'] = bid
    if booking_status:
        filter_query['booking_status'] = booking_status
    if payment_status:
        filter_query['payment_status'] = payment_status
    if booking_reference:
        filter_query['booking_reference'] = {"$regex": booking_reference, "$options": "i"}
    bookings = await db_ops.get_all(Collections.CUSTOM_BOOKINGS, filter_query, skip=skip, limit=limit)
    return serialize_docs(bookings)


@router.get("/{booking_id}")
async def get_custom_booking(booking_id: str, current_user: dict = Depends(get_current_user)):
    booking = await db_ops.get_by_id(Collections.CUSTOM_BOOKINGS, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Custom booking not found")
    return serialize_doc(booking)


@router.put("/{booking_id}")
async def update_custom_booking(
    booking_id: str,
    booking_update: CustomBookingUpdate,
    current_user: dict = Depends(get_current_user)
):
    update_data = booking_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    booking = await db_ops.get_by_id(Collections.CUSTOM_BOOKINGS, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Custom booking not found")
    updated = await db_ops.update(Collections.CUSTOM_BOOKINGS, booking_id, update_data)
    return serialize_doc(updated)


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_custom_booking(booking_id: str, current_user: dict = Depends(get_current_user)):
    booking = await db_ops.get_by_id(Collections.CUSTOM_BOOKINGS, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Custom booking not found")
    await db_ops.update(Collections.CUSTOM_BOOKINGS, booking_id, {"booking_status": "cancelled"})
