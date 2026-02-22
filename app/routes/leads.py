"""
Leads Management Routes - CRM module for managing customer leads, loans, tasks, and follow-ups
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import datetime, date
from pydantic import BaseModel, Field
from typing import Optional, List
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user

router = APIRouter(prefix="/leads", tags=["Leads Management"])

# ─── Pydantic Models ──────────────────────────────────────────────────────────

class LeadCreate(BaseModel):
    customer_full_name: Optional[str] = None
    contact_number: Optional[str] = None
    passport_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None

    # Classification
    lead_status: str = "new"                      # new | followup | confirmed | lost
    conversion_status: str = "not_converted"       # not_converted | converted_to_booking | lost
    lead_source: Optional[str] = None             # walk-in | call | whatsapp | facebook | referral
    interested_in: Optional[str] = None           # ticket | umrah | visa | hotel | transport
    is_instant: bool = False
    is_internal_task: bool = False
    task_type: Optional[str] = None
    assigned_to: Optional[str] = None

    # Loan fields
    loan_amount: Optional[float] = None
    recovered_amount: Optional[float] = 0
    loan_promise_date: Optional[str] = None
    loan_status: Optional[str] = None             # pending | cleared | overdue

    # Follow-up
    next_followup_date: Optional[str] = None
    next_followup_time: Optional[str] = None
    last_contacted_date: Optional[str] = None
    remarks: Optional[str] = None

    # Booking link
    booking_id: Optional[str] = None
    pex_id: Optional[str] = None

    # Scope
    organization_id: Optional[str] = None
    branch_id: Optional[str] = None
    agency_id: Optional[str] = None
    created_by: Optional[str] = None


class LeadUpdate(BaseModel):
    customer_full_name: Optional[str] = None
    contact_number: Optional[str] = None
    lead_status: Optional[str] = None
    conversion_status: Optional[str] = None
    lead_source: Optional[str] = None
    interested_in: Optional[str] = None
    is_instant: Optional[bool] = None
    is_internal_task: Optional[bool] = None
    task_type: Optional[str] = None
    assigned_to: Optional[str] = None
    loan_amount: Optional[float] = None
    recovered_amount: Optional[float] = None
    loan_promise_date: Optional[str] = None
    loan_status: Optional[str] = None
    next_followup_date: Optional[str] = None
    next_followup_time: Optional[str] = None
    last_contacted_date: Optional[str] = None
    remarks: Optional[str] = None
    booking_id: Optional[str] = None
    pex_id: Optional[str] = None


class FollowUpCreate(BaseModel):
    lead_id: str
    followup_date: Optional[str] = None
    followup_time: Optional[str] = None
    contacted_via: str = "phone"          # phone | whatsapp | email | in-person
    remarks: Optional[str] = None
    next_followup_date: Optional[str] = None
    next_followup_time: Optional[str] = None
    created_by: Optional[str] = None


# ─── Lead Endpoints ───────────────────────────────────────────────────────────

@router.get("/", summary="Get all leads")
async def get_leads(
    organization_id: Optional[str] = Query(None),
    branch_id: Optional[str] = Query(None),
    lead_status: Optional[str] = Query(None),
    conversion_status: Optional[str] = Query(None),
    lead_source: Optional[str] = Query(None),
    interested_in: Optional[str] = Query(None),
    is_instant: Optional[bool] = Query(None),
    is_internal_task: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user)
):
    """Return filtered leads list"""
    filters = {}
    if organization_id:
        filters["organization_id"] = organization_id
    if branch_id:
        filters["branch_id"] = branch_id
    if lead_status:
        filters["lead_status"] = lead_status
    if conversion_status:
        filters["conversion_status"] = conversion_status
    if lead_source:
        filters["lead_source"] = lead_source
    if interested_in:
        filters["interested_in"] = interested_in
    if is_instant is not None:
        filters["is_instant"] = is_instant
    if is_internal_task is not None:
        filters["is_internal_task"] = is_internal_task

    leads = await db_ops.get_all(Collections.LEADS, filters, skip=skip, limit=limit)

    if search:
        q = search.lower()
        leads = [l for l in leads if
                 q in (l.get("customer_full_name") or "").lower() or
                 q in (l.get("contact_number") or "") or
                 q in (l.get("passport_number") or "").lower()]

    return serialize_docs(leads)


@router.post("/", summary="Create lead", status_code=status.HTTP_201_CREATED)
async def create_lead(
    lead: LeadCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new lead"""
    lead_dict = lead.model_dump()
    lead_dict["created_at"] = datetime.utcnow().isoformat()
    lead_dict["updated_at"] = datetime.utcnow().isoformat()
    if not lead_dict.get("created_by"):
        lead_dict["created_by"] = str(current_user.get("id") or current_user.get("_id") or "")

    created = await db_ops.create(Collections.LEADS, lead_dict)
    return serialize_doc(created)


@router.get("/today-followups", summary="Today's follow-ups")
async def get_today_followups(
    organization_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get leads with today's follow-up date"""
    today = date.today().isoformat()
    filters = {"next_followup_date": today}
    if organization_id:
        filters["organization_id"] = organization_id

    leads = await db_ops.get_all(Collections.LEADS, filters)
    return serialize_docs(leads)


@router.get("/overdue-loans", summary="Overdue loans")
async def get_overdue_loans(current_user: dict = Depends(get_current_user)):
    """Get leads with overdue loan recovery dates"""
    today = date.today().isoformat()
    all_leads = await db_ops.get_all(Collections.LEADS, {"loan_status": "pending"})
    overdue = [l for l in all_leads if l.get("loan_promise_date") and l["loan_promise_date"] < today]
    return serialize_docs(overdue)


@router.get("/{lead_id}", summary="Get single lead")
async def get_lead(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Get a single lead by ID"""
    lead = await db_ops.get_by_id(Collections.LEADS, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return serialize_doc(lead)


@router.put("/{lead_id}", summary="Update lead")
async def update_lead(
    lead_id: str,
    updates: LeadUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update lead fields"""
    lead = await db_ops.get_by_id(Collections.LEADS, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow().isoformat()

    updated = await db_ops.update(Collections.LEADS, lead_id, update_data)
    return serialize_doc(updated)


@router.delete("/{lead_id}", summary="Delete lead")
async def delete_lead(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a lead"""
    lead = await db_ops.get_by_id(Collections.LEADS, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    await db_ops.delete(Collections.LEADS, lead_id)
    return {"message": "Lead deleted successfully"}


# ─── Follow-up sub-route ──────────────────────────────────────────────────────

@router.post("/followup/", summary="Add follow-up entry", status_code=status.HTTP_201_CREATED)
async def create_followup(
    fu: FollowUpCreate,
    current_user: dict = Depends(get_current_user)
):
    """Add a follow-up history record and update the lead"""
    lead = await db_ops.get_by_id(Collections.LEADS, fu.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    fu_dict = fu.model_dump()
    fu_dict["created_at"] = datetime.utcnow().isoformat()

    # Save follow-up record
    created = await db_ops.create("lead_followups", fu_dict)

    # Update parent lead
    lead_updates: dict = {"updated_at": datetime.utcnow().isoformat()}
    if fu.next_followup_date:
        lead_updates["next_followup_date"] = fu.next_followup_date
    if fu.next_followup_time:
        lead_updates["next_followup_time"] = fu.next_followup_time
    if fu.followup_date:
        lead_updates["last_contacted_date"] = fu.followup_date
    lead_updates["lead_status"] = "followup"

    await db_ops.update(Collections.LEADS, fu.lead_id, lead_updates)

    return serialize_doc(created)


# ─── Convert / mark lost ──────────────────────────────────────────────────────

@router.put("/{lead_id}/convert", summary="Convert lead to booking")
async def convert_lead(
    lead_id: str,
    booking_id: Optional[str] = None,
    pex_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    lead = await db_ops.get_by_id(Collections.LEADS, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    updates = {
        "conversion_status": "converted_to_booking",
        "lead_status": "confirmed",
        "updated_at": datetime.utcnow().isoformat()
    }
    if booking_id:
        updates["booking_id"] = booking_id
    if pex_id:
        updates["pex_id"] = pex_id

    updated = await db_ops.update(Collections.LEADS, lead_id, updates)
    return {"message": "Lead marked as converted", "lead": serialize_doc(updated)}


@router.put("/{lead_id}/mark-lost", summary="Mark lead as lost")
async def mark_lost(
    lead_id: str,
    remarks: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    lead = await db_ops.get_by_id(Collections.LEADS, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    updates = {
        "lead_status": "lost",
        "conversion_status": "lost",
        "updated_at": datetime.utcnow().isoformat()
    }
    if remarks:
        updates["remarks"] = remarks

    updated = await db_ops.update(Collections.LEADS, lead_id, updates)
    return {"message": "Lead marked as lost", "lead": serialize_doc(updated)}
