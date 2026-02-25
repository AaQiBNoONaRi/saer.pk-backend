"""
Customers Routes - Walk-in customers CRUD + Customer Database aggregation from bookings/leads
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user

router = APIRouter(prefix="/customers", tags=["Customer Management"])

# ─── Models ───────────────────────────────────────────────────────────────────

class WalkInCustomerCreate(BaseModel):
    full_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    passport_number: Optional[str] = None
    source: str = "walk-in"                  # walk-in | referral | call | whatsapp
    is_active: bool = True
    notes: Optional[str] = None
    organization_id: Optional[str] = None
    branch_id: Optional[str] = None
    agency_id: Optional[str] = None

class WalkInCustomerUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


# ─── Walk-in Customers (manual) ───────────────────────────────────────────────

@router.get("/", summary="Get walk-in customers")
async def get_customers(
    organization_id: Optional[str] = Query(None),
    branch_id: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500)
):
    """Return manually added walk-in customers"""
    filters = {}
    if organization_id:
        filters["organization_id"] = organization_id
    if branch_id:
        filters["branch_id"] = branch_id
    if is_active is not None:
        filters["is_active"] = is_active

    customers = await db_ops.get_all(Collections.CUSTOMERS, filters, skip=skip, limit=limit)

    if search:
        q = search.lower()
        customers = [c for c in customers if
                     q in (c.get("full_name") or "").lower() or
                     q in (c.get("phone") or "") or
                     q in (c.get("email") or "").lower()]

    return serialize_docs(customers)


@router.post("/", summary="Add walk-in customer", status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer: WalkInCustomerCreate,
    current_user: dict = Depends(get_current_user)
):
    """Add a new walk-in customer manually"""
    customer_dict = customer.model_dump()
    customer_dict["customer_type"] = "walk-in"
    customer_dict["created_at"] = datetime.utcnow().isoformat()
    customer_dict["updated_at"] = datetime.utcnow().isoformat()
    customer_dict["last_activity"] = datetime.utcnow().isoformat()
    customer_dict["total_spent"] = 0

    created = await db_ops.create(Collections.CUSTOMERS, customer_dict)
    return serialize_doc(created)


@router.get("/{customer_id}", summary="Get single customer")
async def get_customer(customer_id: str):
    customer = await db_ops.get_by_id(Collections.CUSTOMERS, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return serialize_doc(customer)


@router.put("/{customer_id}", summary="Update customer")
async def update_customer(
    customer_id: str,
    updates: WalkInCustomerUpdate,
    current_user: dict = Depends(get_current_user)
):
    customer = await db_ops.get_by_id(Collections.CUSTOMERS, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow().isoformat()

    updated = await db_ops.update(Collections.CUSTOMERS, customer_id, update_data)
    return serialize_doc(updated)


@router.delete("/{customer_id}", summary="Delete customer")
async def delete_customer(customer_id: str, current_user: dict = Depends(get_current_user)):
    customer = await db_ops.get_by_id(Collections.CUSTOMERS, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    await db_ops.delete(Collections.CUSTOMERS, customer_id)
    return {"message": "Customer deleted"}


# ─── Customer Database: Aggregation from Bookings + Leads ────────────────────

@router.get("/database/aggregate", summary="Aggregated customer database from all sources")
async def get_customer_database(
    organization_id: Optional[str] = Query(None),
    source: Optional[str] = Query(None),   # bookings | leads | walk-in | branches
    search: Optional[str] = Query(None)
):
    """
    Aggregate customers from all sources:
    - ticket_bookings → passengers[] (first_name + last_name, passport_no)
    - umrah_bookings  → passengers[] (name, passport_no)
    - custom_bookings → passengers[] 
    - leads           → customer_full_name, contact_number
    - customers       → walk-in customers
    """
    all_customers = []
    seen_passports = set()
    seen_phones = set()

    # ── 1. From ticket bookings ───────────────────────────────────────
    if not source or source == "bookings":
        filters = {}
        if organization_id:
            filters["organization_id"] = organization_id

        ticket_bookings = await db_ops.get_all(Collections.TICKET_BOOKINGS, filters, limit=500)
        for booking in ticket_bookings:
            booking_ref = booking.get("booking_reference", "")
            booking_date = booking.get("created_at", "")
            for idx, pax in enumerate(booking.get("passengers") or []):
                first = pax.get("first_name") or ""
                last  = pax.get("last_name") or ""
                name  = pax.get("name") or f"{first} {last}".strip()
                passport = pax.get("passport_no") or pax.get("passport_number") or ""
                phone  = pax.get("phone") or pax.get("contact") or ""
                email  = pax.get("email") or ""

                # De-duplicate by passport
                if passport and passport in seen_passports:
                    continue
                if passport:
                    seen_passports.add(passport)

                all_customers.append({
                    "id": f"tb-{booking_ref}-{name}-{idx}",
                    "full_name": name or "Unknown Passenger",
                    "phone": phone,
                    "email": email,
                    "city": pax.get("country") or "",
                    "passport_number": passport,
                    "gender": pax.get("gender"),
                    "dob": pax.get("dob"),
                    "source": "bookings",
                    "source_label": "Ticket Booking",
                    "booking_reference": booking_ref,
                    "collected_at": booking_date,
                    "status": "active",
                    "organization_id": booking.get("organization_id"),
                })

        # ── 2. From umrah bookings ────────────────────────────────────
        umrah_bookings = await db_ops.get_all(Collections.UMRAH_BOOKINGS, filters, limit=500)
        for booking in umrah_bookings:
            booking_ref = booking.get("booking_reference", "")
            booking_date = booking.get("created_at", "")
            for idx, pax in enumerate(booking.get("passengers") or []):
                first = pax.get("first_name") or ""
                last  = pax.get("last_name") or ""
                name  = pax.get("name") or f"{first} {last}".strip()
                passport = pax.get("passport_no") or pax.get("passport_number") or ""
                phone  = pax.get("phone") or ""
                email  = pax.get("email") or ""

                if passport and passport in seen_passports:
                    continue
                if passport:
                    seen_passports.add(passport)

                all_customers.append({
                    "id": f"ub-{booking_ref}-{name}-{idx}",
                    "full_name": name or "Unknown Passenger",
                    "phone": phone,
                    "email": email,
                    "city": "",
                    "passport_number": passport,
                    "source": "bookings",
                    "source_label": "Umrah Booking",
                    "booking_reference": booking_ref,
                    "collected_at": booking_date,
                    "status": "active",
                    "organization_id": booking.get("organization_id"),
                })

        # ── 3. From custom bookings ───────────────────────────────────
        custom_bookings = await db_ops.get_all(Collections.CUSTOM_BOOKINGS, filters, limit=500)
        for booking in custom_bookings:
            booking_ref = booking.get("booking_reference", "")
            booking_date = booking.get("created_at", "")
            for idx, pax in enumerate(booking.get("passengers") or []):
                first = pax.get("first_name") or ""
                last  = pax.get("last_name") or ""
                name  = pax.get("name") or f"{first} {last}".strip()
                passport = pax.get("passport_no") or pax.get("passport_number") or ""
                phone  = pax.get("phone") or ""
                email  = pax.get("email") or ""

                if passport and passport in seen_passports:
                    continue
                if passport:
                    seen_passports.add(passport)

                all_customers.append({
                    "id": f"cb-{booking_ref}-{name}-{idx}",
                    "full_name": name or "Unknown Passenger",
                    "phone": phone,
                    "email": email,
                    "city": "",
                    "passport_number": passport,
                    "source": "bookings",
                    "source_label": "Custom Booking",
                    "booking_reference": booking_ref,
                    "collected_at": booking_date,
                    "status": "active",
                    "organization_id": booking.get("organization_id"),
                })

    # ── 4. From leads ─────────────────────────────────────────────────
    if not source or source == "leads":
        leads_filters = {}
        if organization_id:
            leads_filters["organization_id"] = organization_id
        leads = await db_ops.get_all(Collections.LEADS, leads_filters, limit=500)
        for lead in leads:
            phone = lead.get("contact_number") or ""
            if phone and phone in seen_phones:
                continue
            if phone:
                seen_phones.add(phone)
            passport = lead.get("passport_number") or ""
            if passport and passport in seen_passports:
                continue
            if passport:
                seen_passports.add(passport)

            all_customers.append({
                "id": f"lead-{lead.get('_id') or lead.get('id') or phone}",
                "full_name": lead.get("customer_full_name") or "Unknown",
                "phone": phone,
                "email": lead.get("email") or "",
                "city": "",
                "passport_number": passport,
                "source": "leads",
                "source_label": "Lead",
                "collected_at": lead.get("created_at") or "",
                "status": "active" if lead.get("lead_status") != "lost" else "inactive",
                "organization_id": lead.get("organization_id"),
            })

    # ── 5. Walk-in customers ──────────────────────────────────────────
    if not source or source == "walk-in":
        walkin_filters = {}
        if organization_id:
            walkin_filters["organization_id"] = organization_id
        walk_ins = await db_ops.get_all(Collections.CUSTOMERS, walkin_filters, limit=500)
        for c in walk_ins:
            phone = c.get("phone") or ""
            if phone and phone in seen_phones:
                continue
            if phone:
                seen_phones.add(phone)
            all_customers.append({
                "id": str(c.get("_id") or c.get("id") or ""),
                "full_name": c.get("full_name") or "Unknown",
                "phone": phone,
                "email": c.get("email") or "",
                "city": c.get("city") or "",
                "passport_number": c.get("passport_number") or "",
                "source": "walk-in",
                "source_label": "Walk-In",
                "collected_at": c.get("created_at") or "",
                "status": "active" if c.get("is_active") is not False else "inactive",
                "organization_id": c.get("organization_id"),
            })

    # ── Apply search ──────────────────────────────────────────────────
    if search:
        q = search.lower()
        all_customers = [c for c in all_customers if
                         q in (c.get("full_name") or "").lower() or
                         q in (c.get("phone") or "") or
                         q in (c.get("passport_number") or "").lower() or
                         q in (c.get("email") or "").lower()]

    # ── Stats ─────────────────────────────────────────────────────────
    from_bookings = [c for c in all_customers if c["source"] == "bookings"]
    from_leads    = [c for c in all_customers if c["source"] == "leads"]
    from_walkin   = [c for c in all_customers if c["source"] == "walk-in"]

    return {
        "total": len(all_customers),
        "from_bookings": len(from_bookings),
        "from_leads":    len(from_leads),
        "from_walkin":   len(from_walkin),
        "customers": all_customers
    }


# ─── Sync endpoint (manually trigger aggregation and save) ───────────────────
@router.post("/database/sync", summary="Sync customer database from all sources")
async def sync_customer_database(
    organization_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Sync aggregated customers into the customer_database collection for faster querying.
    Returns how many new unique customers were added.
    """
    # Use the aggregate endpoint logic inline
    # (For future: insert unique records into customer_database collection)
    return {
        "message": "Sync triggered. The /database/aggregate endpoint always returns live data.",
        "synced_at": datetime.utcnow().isoformat()
    }
