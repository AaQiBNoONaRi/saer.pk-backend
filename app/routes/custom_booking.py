"""
Custom Package Booking routes - self-contained, no BookingCreate model dependency
"""
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from typing import List, Optional, Dict, Any
from datetime import datetime
import random, string, os, shutil
from pydantic import BaseModel, Field

from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user
from app.services.service_charge_logic import get_branch_service_charge, apply_ticket_charge, apply_package_charge, apply_hotel_charge
from app.services.commission_service import create_commission_records
from app.finance.journal_engine import create_custom_booking_journal

router = APIRouter(prefix="/custom-bookings", tags=["Custom Bookings"])

# ── Pydantic models ──────────────────────────────────────────────────────────

class CustomPassengerData(BaseModel):
    model_config = {"extra": "allow"}
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
    # ── Per-passenger service status tracking ──
    visa_status: Optional[str] = "Pending"       # Pending / Approved / Rejected
    ticket_status: Optional[str] = "Pending"     # Pending / Confirmed / Cancelled
    hotel_status: Optional[str] = "Pending"      # Pending / Checked In / Checked Out
    food_status: Optional[str] = "Pending"       # Pending / Served
    ziyarat_status: Optional[str] = "Pending"    # Pending / Completed
    transport_status: Optional[str] = "Pending"  # Pending / Departed
    # ── Shirka (Saudi company) — filled during order delivery ──
    shirka: Optional[str] = None

class CustomRoomSelection(BaseModel):
    model_config = {"extra": "allow"}
    family_id: Optional[str] = None
    hotel_id: Optional[str] = None
    hotel_name: Optional[str] = None
    city: Optional[str] = None
    room_type: str
    quantity: int
    nights: Optional[int] = 0
    rate_sar: Optional[float] = 0
    rate_pkr: Optional[float] = 0
    # ── Hotel voucher — filled during order delivery ──
    hotel_voucher_number: Optional[str] = None
    hotel_brn: Optional[str] = None

class CustomBookingCreate(BaseModel):
    model_config = {"extra": "allow"}
    package_details: Optional[Dict[str, Any]] = None   # full calculator state snapshot
    rooms_selected: List[CustomRoomSelection] = []
    passengers: List[CustomPassengerData] = []
    total_passengers: int = 0
    total_amount: float = 0
    discount_group_id: Optional[str] = None  # ID of the discount group applied
    discount_amount: Optional[float] = 0     # Calculated discount amount
    payment_details: Optional[Dict[str, Any]] = Field(default_factory=dict)
    booking_status: str = "underprocess"
    # Voucher status — starts as Draft, updated during delivery
    voucher_status: Optional[str] = "Draft"
    notes: Optional[str] = None
    agency_details: Optional[Dict[str, Any]] = None
    branch_details: Optional[Dict[str, Any]] = None
    organization_details: Optional[Dict[str, Any]] = None
    # ── Food & Ziyarat vouchers ──
    food_voucher_number: Optional[str] = None
    food_brn: Optional[str] = None
    ziyarat_voucher_number: Optional[str] = None
    ziyarat_brn: Optional[str] = None
    # ── SAR/PKR dual pricing ──────────────────────────────────────────────────
    # Exchange rate snapshot (1 SAR = X PKR at time of booking)
    sar_to_pkr_rate: Optional[float] = None
    # Per-service: _sar = original SAR amount (null if service is PKR-based)
    #              _pkr = final PKR amount always populated
    visa_cost_sar: Optional[float] = None
    visa_cost_pkr: Optional[float] = None
    hotel_cost_sar: Optional[float] = None
    hotel_cost_pkr: Optional[float] = None
    transport_cost_sar: Optional[float] = None
    transport_cost_pkr: Optional[float] = None
    food_cost_sar: Optional[float] = None
    food_cost_pkr: Optional[float] = None
    ziyarat_cost_sar: Optional[float] = None
    ziyarat_cost_pkr: Optional[float] = None

class CustomBookingUpdate(BaseModel):
    model_config = {"extra": "allow"}
    booking_status: Optional[str] = None
    voucher_status: Optional[str] = None
    payment_details: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    passengers: Optional[List[CustomPassengerData]] = None
    rooms_selected: Optional[List[CustomRoomSelection]] = None
    shirka: Optional[str] = None
    package_details: Optional[Dict[str, Any]] = None
    # ── Transport voucher — filled during order delivery ──
    transport_voucher_number: Optional[str] = None
    transport_brn: Optional[str] = None
    food_voucher_number: Optional[str] = None
    food_brn: Optional[str] = None
    ziyarat_voucher_number: Optional[str] = None
    ziyarat_brn: Optional[str] = None

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
    # Set payment deadline (e.g., 3 hours from now)
    from datetime import timedelta
    booking_dict['payment_deadline'] = (datetime.utcnow() + timedelta(hours=3)).isoformat() + "Z"

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

    # ── Record Booker Identity ──
    booking_dict['booked_by_role'] = role
    booking_dict['booked_by_id'] = current_user.get('sub')
    booking_dict['booked_by_name'] = (
        current_user.get('name') or 
        current_user.get('agency_name') or 
        current_user.get('branch_name') or 
        current_user.get('email', 'Unknown')
    )

    # ── If branch/employee books directly, ensure agency_id is null ──
    is_branch_user = (role == 'branch') or (current_user.get('entity_type') == 'branch')
    is_agency_user = (role == 'agency')
    
    if is_branch_user:
        booking_dict['agency_id'] = None
        
    # ── Service Charge Enforcement for Branch and Area Agency users ──
    agency_type = current_user.get('agency_type')
    if is_branch_user or (is_agency_user and agency_type == 'area'):
        branch_id_for_sc = branch_id or current_user.get('entity_id')
        rule = await get_branch_service_charge(branch_id_for_sc)
        if rule:
            total_sc = 0
            
            # 1. Apply Hotel Charges (Overrides)
            for room in booking_dict.get('rooms_selected', []):
                hotel_id = room.get('hotel_id')
                rtype = room.get('room_type', 'sharing').lower()
                base_p = room.get('price_per_person', 0)
                
                inclusive_p = apply_hotel_charge(base_p, rule, hotel_id, rtype)
                room['price_per_person'] = inclusive_p
                total_sc += (inclusive_p - base_p) * room.get('quantity', 0)
            
            # 2. Recalculate total with hotel charges before applying package charge
            current_total = booking_dict.get('total_amount', 0)
            mid_total = current_total + sum((r['price_per_person'] - (r.get('base_price') or r['price_per_person'])) * r.get('quantity', 0) for r in booking_dict.get('rooms_selected', []))
            # Actually simpler: just apply the package charge to the (already increased) total
            # But the total_amount in payload might not have the increments yet.
            
            # Refined: Add the hotel increases to total_amount first
            total_hotel_inc = sum((apply_hotel_charge(r.get('price_per_person', 0), rule, r.get('hotel_id'), r.get('room_type', 'sharing').lower()) - r.get('price_per_person', 0)) * r.get('quantity', 0) for r in booking_dict.get('rooms_selected', []))
            # Wait, I already updated room['price_per_person'] above. 
            # I should just use total_sc so far.
            
            booking_dict['total_amount'] += total_sc 
            
            # 3. Apply Overall Package Charge
            has_package_elements = bool(booking_dict.get('rooms_selected')) or bool(booking_dict.get('visa_cost_pkr'))
            
            updated_total = booking_dict.get('total_amount', 0)
            if has_package_elements:
                final_total = apply_package_charge(updated_total, rule)
                total_sc += (final_total - updated_total)
                booking_dict['total_amount'] = final_total
                
            booking_dict['total_service_charge'] = total_sc
            print(f"DEBUG: Applied Custom Service Charge of {total_sc} to booking. New Total: {booking_dict['total_amount']}")

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

    # ── resolve flight ID → full flight doc so pricing is always available ──
    pkg_details = booking_dict.get('package_details') or {}
    flight_ref = pkg_details.get('flight')
    if isinstance(flight_ref, str) and flight_ref:
        flight_doc = await db_ops.get_by_id(Collections.FLIGHTS, flight_ref)
        if flight_doc:
            booking_dict['package_details']['flight'] = serialize_doc(flight_doc)

    # ── resolve transport ID → full transport doc ──
    transport_ref = pkg_details.get('transport')
    if isinstance(transport_ref, str) and transport_ref:
        transport_doc = await db_ops.get_by_id(Collections.TRANSPORT, transport_ref)
        if transport_doc:
            transport_obj = serialize_doc(transport_doc)
        else:
            transport_obj = {'id': transport_ref}
        transport_obj.setdefault('brn', None)
        transport_obj.setdefault('voucher_no', None)
        booking_dict['package_details']['transport'] = transport_obj
    elif isinstance(transport_ref, dict):
        booking_dict['package_details']['transport'].setdefault('brn', None)
        booking_dict['package_details']['transport'].setdefault('voucher_no', None)

    # ── resolve food ID → full food doc ──
    food_ref = pkg_details.get('food') or pkg_details.get('fooding')
    food_key = 'food' if 'food' in pkg_details else ('fooding' if 'fooding' in pkg_details else 'food')
    if isinstance(food_ref, str) and food_ref:
        food_doc = await db_ops.get_by_id(Collections.FOOD_PRICES, food_ref)
        if food_doc:
            food_obj = serialize_doc(food_doc)
        else:
            food_obj = {'id': food_ref}
        food_obj.setdefault('brn', None)
        food_obj.setdefault('voucher_no', None)
        booking_dict['package_details'][food_key] = food_obj
    elif isinstance(food_ref, dict):
        booking_dict['package_details'][food_key].setdefault('brn', None)
        booking_dict['package_details'][food_key].setdefault('voucher_no', None)

    # ── resolve ziyarat ID → full ziyarat doc ──
    ziyarat_ref = pkg_details.get('ziyarat') or pkg_details.get('ziarat')
    ziyarat_key = 'ziyarat' if 'ziyarat' in pkg_details else ('ziarat' if 'ziarat' in pkg_details else 'ziyarat')
    if isinstance(ziyarat_ref, str) and ziyarat_ref:
        ziyarat_doc = await db_ops.get_by_id(Collections.ZIARAT_PRICES, ziyarat_ref)
        if ziyarat_doc:
            ziyarat_obj = serialize_doc(ziyarat_doc)
        else:
            ziyarat_obj = {'id': ziyarat_ref}
        ziyarat_obj.setdefault('brn', None)
        ziyarat_obj.setdefault('voucher_no', None)
        booking_dict['package_details'][ziyarat_key] = ziyarat_obj
    elif isinstance(ziyarat_ref, dict):
        booking_dict['package_details'][ziyarat_key].setdefault('brn', None)
        booking_dict['package_details'][ziyarat_key].setdefault('voucher_no', None)

    # ── Initialize top-level voucher fields for order delivery ──
    booking_dict['transport_brn'] = None
    booking_dict['transport_voucher_number'] = None
    booking_dict['food_brn'] = None
    booking_dict['food_voucher_number'] = None
    booking_dict['ziyarat_brn'] = None
    booking_dict['ziyarat_voucher_number'] = None
    booking_dict['hotel_brn'] = None
    booking_dict['hotel_voucher_number'] = None
    booking_dict['shirka'] = None
    booking_dict['voucher_status'] = 'Draft'

    created = await db_ops.create(Collections.CUSTOM_BOOKINGS, booking_dict)
    
    # ── Auto-generate double-entry journal ──────────────────────────────────
    try:
        await create_custom_booking_journal(
            booking=serialize_doc(created),
            organization_id=org_id,
            branch_id=branch_id,
            agency_id=agency_id,
            created_by=booking_dict['created_by'],
        )
    except Exception as je:
        print(f"⚠️  Journal engine warning for {created.get('booking_reference')}: {je}")
        
    # ── Auto-create pending payment for bank/cash ───────────────────────────
    pm_details = booking_dict.get("payment_details") or {}
    pmt_method = pm_details.get("payment_method")
    if pmt_method in ["bank_transfer", "bank", "cash", "bank transfer", "online", "transfer"]:
        payment_doc = {
            "booking_id": str(created.get('_id')),
            "booking_type": "custom",
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
        
    # ── Auto-create commission records (non-blocking) ─────────────────────────
    try:
        await create_commission_records(
            booking=serialize_doc(created),
            booking_type="custom",
            current_user=current_user,
        )
    except Exception as ce:
        print(f"⚠️  Commission engine warning: {ce}")

    return serialize_doc(created)



@router.get("/")
async def get_custom_bookings(
    booking_status: Optional[str] = None,
    payment_status: Optional[str] = None,
    booking_reference: Optional[str] = None,
    organization_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    filter_query = {}

    role = current_user.get('role', '')
    entity_type = (current_user.get('entity_type') or '').lower()

    if role in ('organization', 'org', 'admin', 'super_admin') or entity_type in ('organization', 'org'):
        # Org users see all bookings under their org EXCLUDING those made by child branches/agencies
        oid = organization_id or current_user.get('organization_id') or current_user.get('sub')
        if oid:
            filter_query['organization_id'] = oid
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
    bookings = await db_ops.get_all(Collections.CUSTOM_BOOKINGS, filter_query, skip=skip, limit=limit)
    serialized_bookings = serialize_docs(bookings)
    
    # ── Bulk enrich flight data for display ──
    flight_ids = set()
    for b in serialized_bookings:
        f = (b.get('package_details') or {}).get('flight')
        if isinstance(f, str) and f:
            flight_ids.add(f)
            
    if flight_ids:
        from bson import ObjectId
        flight_docs = await db_ops.get_all(Collections.FLIGHTS, {"_id": {"$in": [ObjectId(fid) if isinstance(fid, str) and len(fid)==24 else fid for fid in list(flight_ids)]}})
        flight_map = {str(f.get('_id') or f.get('id')): serialize_doc(f) for f in flight_docs}
        for b in serialized_bookings:
            f_ref = b.get('package_details', {}).get('flight')
            if isinstance(f_ref, str) and f_ref in flight_map:
                b['package_details']['flight'] = flight_map[f_ref]
                
    return serialized_bookings


@router.get("/{booking_id}")
async def get_custom_booking(booking_id: str, current_user: dict = Depends(get_current_user)):
    booking = await db_ops.get_by_id(Collections.CUSTOM_BOOKINGS, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Custom booking not found")
        
    booking_data = serialize_doc(booking)
    
    # ── Enrich flight ──
    pkg = booking_data.get('package_details') or {}
    flight_ref = pkg.get('flight')
    if isinstance(flight_ref, str) and flight_ref:
        flight_doc = await db_ops.get_by_id(Collections.FLIGHTS, flight_ref)
        if flight_doc:
            booking_data['package_details']['flight'] = serialize_doc(flight_doc)
            
    return booking_data


@router.put("/{booking_id}")
async def update_custom_booking(
    booking_id: str,
    booking_update: CustomBookingUpdate,
    current_user: dict = Depends(get_current_user)
):
    update_data = booking_update.model_dump(exclude_unset=True)
    print(f"DEBUG: update_custom_booking update_data keys: {list(update_data.keys())}")
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    booking = await db_ops.get_by_id(Collections.CUSTOM_BOOKINGS, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Custom booking not found")

    # ── Expand package_details into dot-notation to do a deep merge ──
    # This prevents $set from overwriting the entire package_details object.
    pkg = update_data.pop('package_details', None)
    if pkg and isinstance(pkg, dict):
        for sub_key, sub_val in pkg.items():
            # For nested objects (food, transport, ziyarat), expand further
            if isinstance(sub_val, dict):
                for inner_key, inner_val in sub_val.items():
                    update_data[f'package_details.{sub_key}.{inner_key}'] = inner_val
            else:
                update_data[f'package_details.{sub_key}'] = sub_val

    updated = await db_ops.update(Collections.CUSTOM_BOOKINGS, booking_id, update_data)
    return serialize_doc(updated)


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_custom_booking(booking_id: str, current_user: dict = Depends(get_current_user)):
    booking = await db_ops.get_by_id(Collections.CUSTOM_BOOKINGS, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Custom booking not found")
    await db_ops.update(Collections.CUSTOM_BOOKINGS, booking_id, {"booking_status": "cancelled"})
