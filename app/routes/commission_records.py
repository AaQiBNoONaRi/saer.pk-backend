"""
Commission Records API routes – backend-only administration of the
Pending → Earned → Paid lifecycle. No commission data is exposed
to the booking-facing frontend.
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

from app.models.commission_record import CommissionRecordResponse, MarkEarnedRequest, PayoutRequest
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user
from app.finance.journal_engine import create_journal_entry, _resolve_account

router = APIRouter(prefix="/commission-records", tags=["Commission Records"])


# ─── List ─────────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[CommissionRecordResponse])
async def list_commission_records(
    status_filter: Optional[str] = Query(None, alias="status"),
    earner_type:   Optional[str] = None,
    earner_id:     Optional[str] = None,
    branch_id:     Optional[str] = None,
    agency_id:     Optional[str] = None,
    booking_type:  Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
):
    """List commission records with optional filters."""
    query: dict = {}
    if status_filter: query["status"] = status_filter
    if earner_type:   query["earner_type"] = earner_type
    if earner_id:     query["earner_id"] = earner_id
    if branch_id:     query["branch_id"] = branch_id
    if agency_id:     query["agency_id"] = agency_id
    if booking_type:  query["booking_type"] = booking_type

    records = await db_ops.get_all(Collections.COMMISSION_RECORDS, query, skip=skip, limit=limit)
    return serialize_docs(records)


# ─── Detail ───────────────────────────────────────────────────────────────────

@router.get("/{record_id}", response_model=CommissionRecordResponse)
async def get_commission_record(
    record_id: str,
    current_user: dict = Depends(get_current_user),
):
    record = await db_ops.get_by_id(Collections.COMMISSION_RECORDS, record_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commission record not found")
    return serialize_doc(record)


# ─── Mark as Earned ───────────────────────────────────────────────────────────

@router.post("/{record_id}/mark-earned", response_model=CommissionRecordResponse)
async def mark_commission_earned(
    record_id: str,
    body: MarkEarnedRequest = MarkEarnedRequest(),
    current_user: dict = Depends(get_current_user),
):
    """Advance a PENDING commission to EARNED once the trip is confirmed complete."""
    record = await db_ops.get_by_id(Collections.COMMISSION_RECORDS, record_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commission record not found")

    if record.get("status") != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot mark as earned: current status is '{record.get('status')}'",
        )

    now = datetime.utcnow()
    updated = await db_ops.update(Collections.COMMISSION_RECORDS, record_id, {
        "status": "earned",
        "trip_completion_date": body.trip_completion_date or now,
        "updated_at": now,
    })
    return serialize_doc(updated)


# ─── Process Payout ───────────────────────────────────────────────────────────

@router.post("/{record_id}/payout", response_model=CommissionRecordResponse)
async def process_commission_payout(
    record_id: str,
    body: PayoutRequest = PayoutRequest(),
    current_user: dict = Depends(get_current_user),
):
    """
    Move an EARNED commission to PAID.
    Writes a double-entry journal:
        DR  Commission Expense   amount
        CR  Commissions Payable  amount
    """
    record = await db_ops.get_by_id(Collections.COMMISSION_RECORDS, record_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commission record not found")

    if record.get("status") != "earned":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot process payout: current status is '{record.get('status')}' (must be 'earned')",
        )

    amount      = float(record.get("commission_amount", 0))
    org_id      = record.get("organization_id")
    earner_name = record.get("earner_name", "Unknown")
    booking_ref = record.get("booking_reference", "")

    # ── Write journal entry ────────────────────────────────────────────────────
    journal_id = None
    try:
        expense_acct  = await _resolve_account(org_id, "Commission Expense")
        payable_acct  = await _resolve_account(org_id, "Commissions Payable")

        if expense_acct and payable_acct and amount > 0:
            journal = await create_journal_entry(
                reference_type="adjustment",
                reference_id=booking_ref,
                description=f"Commission payout – {earner_name} – {booking_ref}",
                entries=[
                    {
                        "account_id":   expense_acct["_id"],
                        "account_code": expense_acct.get("code"),
                        "account_name": expense_acct.get("name"),
                        "debit":        amount,
                        "credit":       0.0,
                        "description":  f"Commission to {earner_name}",
                    },
                    {
                        "account_id":   payable_acct["_id"],
                        "account_code": payable_acct.get("code"),
                        "account_name": payable_acct.get("name"),
                        "debit":        0.0,
                        "credit":       amount,
                        "description":  f"Commissions Payable – {earner_name}",
                    },
                ],
                organization_id=org_id,
                branch_id=record.get("branch_id"),
                agency_id=record.get("agency_id"),
                created_by=current_user.get("sub", "system"),
            )
            journal_id = journal.get("_id") or journal.get("id")
    except Exception as e:
        print(f"⚠️ Commission journal warning: {e}")

    now = datetime.utcnow()
    updated = await db_ops.update(Collections.COMMISSION_RECORDS, record_id, {
        "status":            "paid",
        "paid_at":           now,
        "paid_by":           current_user.get("sub"),
        "journal_entry_id":  journal_id,
        "updated_at":        now,
    })
    return serialize_doc(updated)


# ─── Summary stats helper ─────────────────────────────────────────────────────

@router.get("/summary/totals")
async def commission_summary(
    branch_id:    Optional[str] = None,
    agency_id:    Optional[str] = None,
    earner_id:    Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Return quick totals grouped by status for dashboard widgets."""
    base_query: dict = {}
    if branch_id:  base_query["branch_id"]  = branch_id
    if agency_id:  base_query["agency_id"]  = agency_id
    if earner_id:  base_query["earner_id"]  = earner_id

    coll = db_config.get_collection(Collections.COMMISSION_RECORDS)
    totals = {"pending": 0.0, "earned": 0.0, "paid": 0.0, "count": 0}

    async for doc in coll.find(base_query):
        s = doc.get("status", "pending")
        totals[s] = round(totals.get(s, 0) + float(doc.get("commission_amount", 0)), 2)
        totals["count"] += 1

    return totals


# ── import needed for summary endpoint ────────────────────────────────────────
from app.config.database import db_config
