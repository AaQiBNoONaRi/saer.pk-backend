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
    whatsapp_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None

    # Classification
    lead_status: str = "new"                      # new | followup | confirmed | lost
    conversion_status: str = "not_converted"       # not_converted | converted_to_booking | lost
    lead_source: Optional[str] = None             # walk-in | call | whatsapp | facebook | referral
    interested_in: Optional[str] = None           # ticket | umrah | visa | hotel | transport
    is_instant: bool = False
    is_internal_task: bool = False
   

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

    # Scope
    organization_id: Optional[str] = None
    branch_id: Optional[str] = None
    agency_id: Optional[str] = None
    created_by: Optional[str] = None
    employee_id: Optional[str] = None


class LeadUpdate(BaseModel):
    customer_full_name: Optional[str] = None
    contact_number: Optional[str] = None
    whatsapp_number: Optional[str] = None
    customer_id: Optional[str] = None
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
    city: Optional[str] = None
    country: Optional[str] = None


class FollowUpCreate(BaseModel):
    lead_id: str
    followup_date: Optional[str] = None
    followup_time: Optional[str] = None
    contacted_via: str = "phone"          # phone | whatsapp | email | in-person
    remarks: Optional[str] = None
    next_followup_date: Optional[str] = None
    next_followup_time: Optional[str] = None
    created_by: Optional[str] = None


class RemarkCreate(BaseModel):
    text: str = Field(..., min_length=1, description="Remark content")


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
    limit: int = Query(100, ge=1, le=500)
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
                 q in (l.get("whatsapp_number") or "") or
                 q in (l.get("city") or "").lower() or
                 q in (l.get("country") or "").lower() or
                 q in (l.get("email") or "").lower()]

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
    lead_dict["chat_remarks"] = []  # chat-style remarks list
    entity_type = current_user.get("entity_type")
    entity_id = current_user.get("entity_id")
    
    if entity_type == "organization":
        if not lead_dict.get("organization_id"): lead_dict["organization_id"] = str(entity_id)
    elif entity_type == "branch":
        if not lead_dict.get("branch_id"): lead_dict["branch_id"] = str(entity_id)
        if not lead_dict.get("organization_id") and current_user.get("organization_id"):
            lead_dict["organization_id"] = str(current_user.get("organization_id"))
    elif entity_type == "agency":
        if not lead_dict.get("agency_id"): lead_dict["agency_id"] = str(entity_id)
        if not lead_dict.get("organization_id") and current_user.get("organization_id"):
            lead_dict["organization_id"] = str(current_user.get("organization_id"))

    # Fallbacks for standard formats
    if not lead_dict.get("organization_id") and current_user.get("organization_id"):
        lead_dict["organization_id"] = str(current_user.get("organization_id"))
    if not lead_dict.get("branch_id") and current_user.get("branch_id"):
        lead_dict["branch_id"] = str(current_user.get("branch_id"))
    if not lead_dict.get("agency_id") and current_user.get("agency_id"):
        lead_dict["agency_id"] = str(current_user.get("agency_id"))

    # Set created_by from token: prefer _id (MongoDB ObjectId), then sub (admin), then emp_id (string format)
    if not lead_dict.get("created_by"):
        created_by = current_user.get("_id") or current_user.get("sub") or current_user.get("emp_id") or current_user.get("id") or ""
        lead_dict["created_by"] = str(created_by)
        
    if current_user.get("user_type") == "employee" and current_user.get("_id"):
        lead_dict["employee_id"] = current_user.get("_id")

    created = await db_ops.create(Collections.LEADS, lead_dict)
    return serialize_doc(created)


@router.get("/today-followups", summary="Today's follow-ups")
async def get_today_followups(
    organization_id: Optional[str] = Query(None)
):
    """Get leads with today's follow-up date"""
    today = date.today().isoformat()
    filters = {"next_followup_date": today}
    if organization_id:
        filters["organization_id"] = organization_id

    leads = await db_ops.get_all(Collections.LEADS, filters)
    return serialize_docs(leads)


@router.get("/overdue-loans", summary="Overdue loans")
async def get_overdue_loans():
    """Get leads with overdue loan recovery dates"""
    today = date.today().isoformat()
    all_leads = await db_ops.get_all(Collections.LEADS, {"loan_status": "pending"})
    overdue = [l for l in all_leads if l.get("loan_promise_date") and l["loan_promise_date"] < today]
    return serialize_docs(overdue)


@router.get("/{lead_id}", summary="Get single lead")
async def get_lead(lead_id: str):
    """Get a single lead by ID"""
    lead = await db_ops.get_by_id(Collections.LEADS, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return serialize_doc(lead)


@router.put("/{lead_id}", summary="Update lead")
async def update_lead(
    lead_id: str,
    updates: LeadUpdate,
):
    """Update lead fields — open endpoint, no authentication required"""
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


@router.post("/{lead_id}/remarks", summary="Add a remark to a lead")
async def add_lead_remark(
    lead_id: str,
    remark: RemarkCreate,
    current_user: dict = Depends(get_current_user)
):
    """Append a chat-style remark to a lead"""
    lead = await db_ops.get_by_id(Collections.LEADS, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    author_name = await _get_author_name(current_user)
    # Use user_type for the badge (employee/organization/branch/agency)
    # entity_type in the token means which scope they belong to, not their role
    author_type = current_user.get("user_type", "unknown")
    remark_entity_type = author_type   # e.g. "employee", "organization"
    entity_name = _get_entity_name(current_user)

    remark_entry = {
        "text": remark.text.strip(),
        "author_name": author_name,
        "author_type": author_type,
        "entity_type": remark_entity_type,
        "entity_name": entity_name,
        "created_at": datetime.utcnow().isoformat(),
    }

    existing_remarks = lead.get("chat_remarks", [])
    if not isinstance(existing_remarks, list):
        existing_remarks = []
    existing_remarks.append(remark_entry)

    await db_ops.update(Collections.LEADS, lead_id, {
        "chat_remarks": existing_remarks,
        "updated_at": datetime.utcnow().isoformat()
    })

    return {"success": True, "remark": remark_entry}



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


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_author_name(current_user: dict) -> str:
    """Get a human-readable name for the logged-in user dynamically from the database."""
    from app.database.db_operations import db_ops
    from app.config.database import Collections
    try:
        if current_user.get("user_type") == "employee":
            emp_id = current_user.get("_id") or current_user.get("emp_id")
            if emp_id:
                emp = await db_ops.get_by_id(Collections.EMPLOYEES, emp_id)
                if not emp and current_user.get("emp_id"):
                    emp = await db_ops.get_one(Collections.EMPLOYEES, {"emp_id": current_user["emp_id"]})
                if emp:
                    return emp.get("full_name") or emp.get("name") or emp.get("email") or emp.get("emp_id") or "Employee"
        
        if current_user.get("user_type") in ["admin", "organization"]:
            coll = Collections.ADMINS if current_user.get("user_type") == "admin" else Collections.ORGANIZATIONS
            sub_id = current_user.get("sub") or current_user.get("_id")
            if sub_id:
                user = await db_ops.get_by_id(coll, sub_id)
                if user:
                    return user.get("full_name") or user.get("name") or user.get("username") or user.get("email") or current_user.get("user_type", "").title()

        role = current_user.get("role", "")
        if role in ["branch", "agency"]:
            coll = Collections.BRANCHES if role == "branch" else Collections.AGENCIES
            sub_id = current_user.get("sub") or current_user.get("_id")
            if sub_id:
                user = await db_ops.get_by_id(coll, sub_id)
                if user:
                    return user.get("full_name") or user.get("name") or user.get("email") or role.title()
    except Exception as e:
        print(f"Error fetching live author name: {e}")

    # Fallback to token payload if DB lookup fails
    return (
        current_user.get("full_name")
        or current_user.get("name")
        or current_user.get("username")
        or current_user.get("email")
        or "User"
    )


def _get_entity_name(current_user: dict) -> str:
    """Get a descriptive label for the entity - role for employees, org/branch/agency name for others."""
    user_type = current_user.get("user_type", "")
    # For employees, show their role/designation within their org
    if user_type == "employee":
        return (
            current_user.get("role")
            or current_user.get("designation")
            or current_user.get("entity_type", "").title()  # e.g. Organization, Branch
            or "Employee"
        )
    # For org/branch/agency portal admins, show the entity name
    entity_type = current_user.get("entity_type", "")
    if entity_type == "organization":
        return (
            current_user.get("org_name")
            or current_user.get("organization_name")
            or current_user.get("username")
            or "Organization"
        )
    if entity_type == "branch":
        return current_user.get("branch_name") or current_user.get("branch_city") or "Branch"
    if entity_type == "agency":
        return current_user.get("agency_name") or "Agency"
    return current_user.get("role") or current_user.get("user_type") or ""


