"""
Passport Leads Management Routes - Track passport applications and follow-ups within the CRM
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user

router = APIRouter(prefix="/passport-leads", tags=["Passport Leads"])

# ─── Pydantic Models ──────────────────────────────────────────────────────────

class PassportLeadCreate(BaseModel):
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    passport_number: Optional[str] = None
    email: Optional[str] = None

    service_type: Optional[str] = None          # umrah | visa | hajj | tourism
    travel_date: Optional[str] = None
    return_date: Optional[str] = None

    status: str = "pending"                      # pending | processing | completed | rejected | converted
    remarks: Optional[str] = None

    # Follow-up tracking
    next_followup_date: Optional[str] = None
    last_contacted_date: Optional[str] = None

    # Booking link if converted
    booking_id: Optional[str] = None

    # Scope
    organization_id: Optional[str] = None
    branch_id: Optional[str] = None
    agency_id: Optional[str] = None
    created_by: Optional[str] = None


class PassportLeadUpdate(BaseModel):
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    passport_number: Optional[str] = None
    service_type: Optional[str] = None
    travel_date: Optional[str] = None
    return_date: Optional[str] = None
    status: Optional[str] = None
    remarks: Optional[str] = None
    next_followup_date: Optional[str] = None
    last_contacted_date: Optional[str] = None
    booking_id: Optional[str] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/", summary="Get all passport leads")
async def get_passport_leads(
    organization_id: Optional[str] = Query(None),
    branch_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    service_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user)
):
    """Return filtered passport leads list"""
    filters = {}
    if organization_id:
        filters["organization_id"] = organization_id
    if branch_id:
        filters["branch_id"] = branch_id
    if status:
        filters["status"] = status
    if service_type:
        filters["service_type"] = service_type

    records = await db_ops.get_all(Collections.PASSPORT_LEADS, filters, skip=skip, limit=limit)

    if search:
        q = search.lower()
        records = [r for r in records if
                   q in (r.get("customer_name") or "").lower() or
                   q in (r.get("customer_phone") or "") or
                   q in (r.get("passport_number") or "").lower()]

    return serialize_docs(records)


@router.post("/", summary="Create passport lead", status_code=status.HTTP_201_CREATED)
async def create_passport_lead(
    lead: PassportLeadCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new passport lead"""
    lead_dict = lead.model_dump()
    lead_dict["created_at"] = datetime.utcnow().isoformat()
    lead_dict["updated_at"] = datetime.utcnow().isoformat()
    if not lead_dict.get("created_by"):
        lead_dict["created_by"] = str(current_user.get("id") or current_user.get("_id") or "")

    created = await db_ops.create(Collections.PASSPORT_LEADS, lead_dict)
    return serialize_doc(created)


@router.get("/{lead_id}", summary="Get single passport lead")
async def get_passport_lead(lead_id: str, current_user: dict = Depends(get_current_user)):
    record = await db_ops.get_by_id(Collections.PASSPORT_LEADS, lead_id)
    if not record:
        raise HTTPException(status_code=404, detail="Passport lead not found")
    return serialize_doc(record)


@router.put("/{lead_id}", summary="Update passport lead")
async def update_passport_lead(
    lead_id: str,
    updates: PassportLeadUpdate,
    current_user: dict = Depends(get_current_user)
):
    record = await db_ops.get_by_id(Collections.PASSPORT_LEADS, lead_id)
    if not record:
        raise HTTPException(status_code=404, detail="Passport lead not found")

    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow().isoformat()

    updated = await db_ops.update(Collections.PASSPORT_LEADS, lead_id, update_data)
    return serialize_doc(updated)


@router.delete("/{lead_id}", summary="Delete passport lead")
async def delete_passport_lead(lead_id: str, current_user: dict = Depends(get_current_user)):
    record = await db_ops.get_by_id(Collections.PASSPORT_LEADS, lead_id)
    if not record:
        raise HTTPException(status_code=404, detail="Passport lead not found")
    await db_ops.delete(Collections.PASSPORT_LEADS, lead_id)
    return {"message": "Passport lead deleted successfully"}
