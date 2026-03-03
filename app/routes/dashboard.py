"""
Branch Dashboard API
--------------------
Single endpoint `GET /api/dashboard/branch/` that returns all live KPIs,
booking-status stats and recent-activity feed for the branch portal.

Works for both branch-user tokens and employee tokens whose entity_type == 'branch'.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from datetime import datetime
import asyncio

from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.auth import get_current_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# ── Status buckets ────────────────────────────────────────────────────────────
DONE_STATUSES      = {'approved', 'done', 'completed'}
BOOKED_STATUSES    = {'confirmed', 'underprocess', 'under_process', 'booked', 'processing'}
CANCELLED_STATUSES = {'cancelled', 'canceled', 'expired', 'rejected'}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_branch_id(current_user: dict) -> Optional[str]:
    """
    Derive branch_id from a JWT regardless of whether the caller is a
    branch-user or an employee whose entity is a branch.
    """
    role = current_user.get('role')
    return (
        current_user.get('branch_id') or
        (current_user.get('sub') if role == 'branch' else None) or
        (current_user.get('entity_id') if current_user.get('entity_type') == 'branch' else None)
    )


def _safe_dt(val) -> Optional[datetime]:
    """Coerce a stored value (datetime or ISO string) to a datetime object."""
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                pass
    return None


def _booking_status_counts(docs: list) -> dict:
    """Return done / booked / cancelled counts for a list of booking docs."""
    done = booked = cancelled = 0
    for doc in docs:
        raw = (doc.get('booking_status') or doc.get('status') or '').lower()
        if raw in DONE_STATUSES:
            done += 1
        elif raw in CANCELLED_STATUSES:
            cancelled += 1
        else:
            booked += 1   # confirmed, underprocess, unknown → Booked
    return {
        "total":     len(docs),
        "done":      done,
        "booked":    booked,
        "cancelled": cancelled,
    }


def _booking_to_activity(doc: dict, type_label: str) -> dict:
    dt = _safe_dt(doc.get('created_at'))
    return {
        "type":         "booking",
        "event":        f"{type_label} Booking Created",
        "reference":    doc.get('booking_reference') or str(doc.get('_id', '')),
        "booking_type": doc.get('booking_type') or type_label.lower(),
        "name":         doc.get('agent_name') or doc.get('created_by') or 'Unknown',
        "amount":       float(doc.get('total_amount') or doc.get('amount') or 0),
        "status":       (doc.get('booking_status') or doc.get('status') or 'unknown').lower(),
        "created_at":   dt.isoformat() if dt else '',
        "_sort_dt":     dt or datetime.min,
    }


def _payment_to_activity(doc: dict) -> dict:
    status = (doc.get('status') or '').lower()
    event = (
        'Payment Approved' if status == 'approved' else
        'Payment Rejected' if status == 'rejected' else
        'Payment Submitted'
    )
    dt = _safe_dt(doc.get('created_at'))
    return {
        "type":         "payment",
        "event":        event,
        "reference":    doc.get('booking_reference') or str(doc.get('_id', '')),
        "booking_type": doc.get('booking_type') or '',
        "name":         doc.get('agent_name') or doc.get('created_by') or 'Unknown',
        "amount":       float(doc.get('amount') or 0),
        "status":       status,
        "created_at":   dt.isoformat() if dt else '',
        "_sort_dt":     dt or datetime.min,
    }


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/branch/")
async def get_branch_dashboard(current_user: dict = Depends(get_current_user)):
    """
    Returns all live data for the branch portal dashboard in a single call:
    - KPIs  : today_bookings, pending_payments, active_employees, monthly_revenue
    - Stats : per-type booking status counts (tickets / umrah / custom)
    - Feed  : top-20 recent activity events (bookings + payments)
    """
    branch_id = _resolve_branch_id(current_user)
    if not branch_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot determine branch from token — please log in again."
        )

    # ── Time boundaries (UTC) ─────────────────────────────────────────────────
    now          = datetime.utcnow()
    today_start  = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start  = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    branch_filter = {"branch_id": branch_id}

    # ── Fire all queries in parallel ──────────────────────────────────────────
    (
        all_tickets,
        all_umrah,
        all_custom,
        all_payments,
        employee_count,
    ) = await asyncio.gather(
        db_ops.get_all(Collections.TICKET_BOOKINGS, branch_filter, limit=5000),
        db_ops.get_all(Collections.UMRAH_BOOKINGS,  branch_filter, limit=5000),
        db_ops.get_all(Collections.CUSTOM_BOOKINGS, branch_filter, limit=5000),
        db_ops.get_all(Collections.PAYMENTS,        branch_filter, limit=5000),
        db_ops.count(Collections.EMPLOYEES, {
            "entity_id":   branch_id,
            "entity_type": "branch",
        }),
    )

    # Concatenate all booking docs for shared iteration
    all_bookings = [*all_tickets, *all_umrah, *all_custom]

    # ── KPI: Today's Bookings ─────────────────────────────────────────────────
    today_bookings = sum(
        1 for d in all_bookings
        if (_safe_dt(d.get('created_at')) or datetime.min) >= today_start
    )

    # ── KPI: Pending Payments ─────────────────────────────────────────────────
    pending = [
        p for p in all_payments
        if (p.get('status') or '').lower() == 'pending'
    ]
    pending_count  = len(pending)
    pending_amount = sum(float(p.get('amount') or 0) for p in pending)

    # ── KPI: Monthly Revenue (approved payments this month) ───────────────────
    monthly_revenue = sum(
        float(p.get('amount') or 0)
        for p in all_payments
        if (p.get('status') or '').lower() == 'approved'
        and (_safe_dt(p.get('created_at')) or datetime.min) >= month_start
    )

    # ── Booking Status Stats ──────────────────────────────────────────────────
    booking_stats = {
        "tickets": _booking_status_counts(all_tickets),
        "umrah":   _booking_status_counts(all_umrah),
        "custom":  _booking_status_counts(all_custom),
    }

    # ── Recent Activity Feed (top 20, newest first) ───────────────────────────
    activities = [
        *[_booking_to_activity(d, "Ticket") for d in all_tickets],
        *[_booking_to_activity(d, "Umrah")  for d in all_umrah],
        *[_booking_to_activity(d, "Custom") for d in all_custom],
        *[_payment_to_activity(p)           for p in all_payments],
    ]
    activities.sort(key=lambda x: x["_sort_dt"], reverse=True)
    for a in activities:
        del a["_sort_dt"]
    recent_activity = activities[:20]

    return {
        "kpis": {
            "today_bookings":          today_bookings,
            "pending_payments_count":  pending_count,
            "pending_payments_amount": round(pending_amount, 2),
            "active_employees":        employee_count,
            "monthly_revenue":         round(monthly_revenue, 2),
        },
        "booking_stats": booking_stats,
        "recent_activity": recent_activity,
    }


# ════════════════════════════════════════════════════════════════════════════
# ORG Dashboard endpoint
# ════════════════════════════════════════════════════════════════════════════

def _resolve_org_id(current_user: dict) -> Optional[str]:
    """Derive organization_id from a JWT — works for org admins and org employees."""
    return (
        current_user.get('organization_id') or
        (current_user.get('entity_id') if current_user.get('entity_type') == 'organization' else None) or
        (current_user.get('sub') if current_user.get('role') in ('organization', 'super_admin') else None)
    )


def _doc_to_booking_summary(doc: dict, type_label: str) -> dict:
    """Convert a booking document to a compact summary dict."""
    dt = _safe_dt(doc.get('created_at'))
    return {
        "reference":    doc.get('booking_reference') or str(doc.get('_id', '')),
        "booking_type": type_label,
        "agent_name":   doc.get('agent_name') or doc.get('created_by') or 'Unknown',
        "amount":       float(doc.get('total_amount') or doc.get('amount') or 0),
        "status":       (doc.get('booking_status') or doc.get('status') or 'unknown').lower(),
        "created_at":   dt.isoformat() if dt else '',
        "_sort_dt":     dt or datetime.min,
    }


def _activity_event(event_type: str, title: str, subtitle: str,
                    navigate_to: str, dt: Optional[datetime],
                    amount: float = 0.0, status: str = '',
                    reference: str = '') -> dict:
    return {
        "event_type":   event_type,
        "title":        title,
        "subtitle":     subtitle,
        "navigate_to":  navigate_to,
        "amount":       round(amount, 2),
        "status":       status,
        "reference":    reference,
        "created_at":   dt.isoformat() if dt else '',
        "_sort_dt":     dt or datetime.min,
    }


def _build_activity(
    all_tickets, all_umrah, all_custom, all_payments,
    all_packages, all_hotels,
    others_docs: list,   # list of (label, navigate_to, doc) tuples
) -> list:
    """Build a merged, sorted activity list from all sources."""
    events: list = []

    # ── Bookings ──────────────────────────────────────────────────────────────
    _BOOKING_META = [
        (all_tickets, "Ticket Booking",  "Tickets"),
        (all_umrah,   "Umrah Package",   "Packages"),
        (all_custom,  "Custom Package",  "Others"),
    ]
    for docs, label, nav in _BOOKING_META:
        for d in docs:
            dt = _safe_dt(d.get('created_at'))
            ref = d.get('booking_reference') or str(d.get('_id', ''))
            agent = d.get('agent_name') or d.get('created_by') or 'Unknown'
            status = (d.get('booking_status') or '').lower()
            events.append(_activity_event(
                event_type  = 'booking_created',
                title       = f"{label} Booked",
                subtitle    = f"{ref} — by {agent}",
                navigate_to = nav,
                dt          = dt,
                amount      = float(d.get('total_amount') or d.get('amount') or 0),
                status      = status,
                reference   = ref,
            ))

    # ── Payments ──────────────────────────────────────────────────────────────
    for p in all_payments:
        status  = (p.get('status') or 'pending').lower()
        created = _safe_dt(p.get('created_at'))
        updated = _safe_dt(p.get('updated_at'))
        agent   = p.get('agent_name') or p.get('created_by') or 'Unknown'
        ref     = p.get('booking_reference') or str(p.get('_id', ''))
        amt     = float(p.get('amount') or 0)

        # Submission event
        events.append(_activity_event(
            event_type  = 'payment_submitted',
            title       = 'Payment Submitted',
            subtitle    = f"{ref} — {agent}",
            navigate_to = 'Finance Hub',
            dt          = created,
            amount      = amt,
            status      = 'pending',
            reference   = ref,
        ))
        # Status-change event (if it moved away from pending)
        if updated and created and updated > created and status != 'pending':
            label = 'Payment Approved' if status == 'approved' else \
                    'Payment Rejected' if status == 'rejected' else \
                    f'Payment {status.capitalize()}'
            events.append(_activity_event(
                event_type  = 'payment_status',
                title       = label,
                subtitle    = f"{ref} — {agent}",
                navigate_to = 'Finance Hub',
                dt          = updated,
                amount      = amt,
                status      = status,
                reference   = ref,
            ))

    # ── Packages ──────────────────────────────────────────────────────────────
    for d in all_packages:
        created = _safe_dt(d.get('created_at'))
        updated = _safe_dt(d.get('updated_at'))
        name    = d.get('title') or d.get('name') or 'Package'
        events.append(_activity_event(
            event_type  = 'package_created' if (not updated or updated == created) else 'package_updated',
            title       = 'Package Created' if (not updated or updated == created) else 'Package Updated',
            subtitle    = name,
            navigate_to = 'Packages',
            dt          = updated or created,
        ))
        # If separately created && then updated → two events
        if updated and created and updated > created:
            events.append(_activity_event(
                event_type  = 'package_created',
                title       = 'Package Created',
                subtitle    = name,
                navigate_to = 'Packages',
                dt          = created,
            ))

    # ── Hotels ────────────────────────────────────────────────────────────────
    for d in all_hotels:
        created = _safe_dt(d.get('created_at'))
        updated = _safe_dt(d.get('updated_at'))
        name    = d.get('name') or 'Hotel'
        events.append(_activity_event(
            event_type  = 'hotel_created' if (not updated or updated == created) else 'hotel_updated',
            title       = 'Hotel Created' if (not updated or updated == created) else 'Hotel Updated',
            subtitle    = name,
            navigate_to = 'Hotels',
            dt          = updated or created,
        ))
        if updated and created and updated > created:
            events.append(_activity_event(
                event_type  = 'hotel_created',
                title       = 'Hotel Created',
                subtitle    = name,
                navigate_to = 'Hotels',
                dt          = created,
            ))

    # ── Others sub-items (shirkas, flight IATA, city IATA, etc.) ─────────────
    for label, nav, d in others_docs:
        created = _safe_dt(d.get('created_at'))
        updated = _safe_dt(d.get('updated_at'))
        name    = (d.get('name') or d.get('airline_name') or d.get('city_name') or
                   d.get('title') or d.get('vehicle_name') or label)
        dt = updated or created
        if not dt:
            continue
        events.append(_activity_event(
            event_type  = 'config_saved',
            title       = f'{label} Saved',
            subtitle    = str(name),
            navigate_to = nav,
            dt          = dt,
        ))

    # ── Sort newest first, strip internal key, cap at 40 ─────────────────────
    events.sort(key=lambda x: x["_sort_dt"], reverse=True)
    for e in events:
        del e["_sort_dt"]
    return events[:40]


@router.get("/org/")
async def get_org_dashboard(current_user: dict = Depends(get_current_user)):
    """
    Returns all live data for the Organization portal dashboard in a single call.

    KPIs       : working_agents, total_agents, new_agents_this_month,
                 recovery_pending, working_employees, total_employees
    Portfolio  : ticket / umrah / custom booking status counts (org-scoped)
    Highlights : last_booking, last_delivery
    Recent     : last 20 bookings across all types (org-scoped)
    Activity   : last 40 events — bookings, payments, packages, hotels, others
    """
    org_id = _resolve_org_id(current_user)
    if not org_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot determine organization from token — please log in again."
        )

    now         = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    org_filter  = {"organization_id": org_id}

    # ── Fire all queries in parallel ──────────────────────────────────────────
    (
        all_tickets,
        all_umrah,
        all_custom,
        all_agents,
        all_payments,
        all_org_employees,
        all_packages,
        all_hotels,
        # Others sub-collections (global, not org-scoped)
        shirkas,
        big_sectors,
        flight_iata,
        city_iata,
        transport_prices,
    ) = await asyncio.gather(
        db_ops.get_all(Collections.TICKET_BOOKINGS, org_filter, limit=10000),
        db_ops.get_all(Collections.UMRAH_BOOKINGS,  org_filter, limit=10000),
        db_ops.get_all(Collections.CUSTOM_BOOKINGS, org_filter, limit=10000),
        db_ops.get_all(Collections.AGENCIES, org_filter, limit=2000),
        db_ops.get_all(Collections.PAYMENTS, org_filter, limit=5000),
        db_ops.get_all(Collections.EMPLOYEES, {
            "entity_type": "organization",
            "entity_id":   org_id,
        }, limit=1000),
        db_ops.get_all("packages", org_filter, limit=500),
        db_ops.get_all("hotels",   org_filter, limit=500),
        db_ops.get_all("shirkas",  {}, limit=200),
        db_ops.get_all("big_sectors", {}, limit=200),
        db_ops.get_all("flight_iata", {}, limit=200),
        db_ops.get_all("city_iata",   {}, limit=200),
        db_ops.get_all("transport_prices", {}, limit=200),
    )

    # ── KPI: Agents ───────────────────────────────────────────────────────────
    working_agents = sum(1 for a in all_agents if a.get('is_active') is True or a.get('status', '').lower() == 'active')
    total_agents   = len(all_agents)
    new_agents     = sum(
        1 for a in all_agents
        if (_safe_dt(a.get('created_at')) or datetime.min) >= month_start
    )

    # ── KPI: Recovery Pending ─────────────────────────────────────────────────
    recovery_amount = sum(
        float(p.get('amount') or 0)
        for p in all_payments
        if (p.get('status') or '').lower() == 'pending'
    )

    # ── KPI: ORG Employees ────────────────────────────────────────────────────
    working_employees = sum(
        1 for e in all_org_employees
        if (e.get('status') or 'active').lower() in ('active', 'working')
    )
    total_employees = len(all_org_employees)

    # ── Portfolio stats ───────────────────────────────────────────────────────
    portfolio = {
        "tickets": _booking_status_counts(all_tickets),
        "umrah":   _booking_status_counts(all_umrah),
        "custom":  _booking_status_counts(all_custom),
    }

    # ── All bookings combined, sorted newest first ────────────────────────────
    all_bookings_raw = [
        *[_doc_to_booking_summary(d, 'ticket') for d in all_tickets],
        *[_doc_to_booking_summary(d, 'umrah')  for d in all_umrah],
        *[_doc_to_booking_summary(d, 'custom') for d in all_custom],
    ]
    all_bookings_raw.sort(key=lambda x: x["_sort_dt"], reverse=True)

    last_booking = None
    if all_bookings_raw:
        lb = dict(all_bookings_raw[0]); del lb["_sort_dt"]; last_booking = lb

    last_delivery = None
    for b in all_bookings_raw:
        if b["status"] in DONE_STATUSES:
            ld = dict(b); del ld["_sort_dt"]; last_delivery = ld; break

    recent_bookings = []
    for b in all_bookings_raw[:20]:
        rb = dict(b); del rb["_sort_dt"]; recent_bookings.append(rb)

    # ── Activity feed ─────────────────────────────────────────────────────────
    others_docs = (
        [("Shirka",          "Others",  d) for d in shirkas]        +
        [("Big Sector",      "Others",  d) for d in big_sectors]    +
        [("Flight IATA",     "Others",  d) for d in flight_iata]    +
        [("City IATA",       "Others",  d) for d in city_iata]      +
        [("Transport Price", "Others",  d) for d in transport_prices]
    )
    recent_activity = _build_activity(
        all_tickets, all_umrah, all_custom, all_payments,
        all_packages, all_hotels, others_docs,
    )

    return {
        "kpis": {
            "working_agents":        working_agents,
            "total_agents":          total_agents,
            "new_agents_this_month": new_agents,
            "recovery_pending":      round(recovery_amount, 2),
            "working_employees":     working_employees,
            "total_employees":       total_employees,
        },
        "portfolio":        portfolio,
        "last_booking":     last_booking,
        "last_delivery":    last_delivery,
        "recent_bookings":  recent_bookings,
        "recent_activity":  recent_activity,
    }
