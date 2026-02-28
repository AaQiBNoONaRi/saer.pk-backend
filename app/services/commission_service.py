"""
Commission Service – the engine that calculates and creates commission records
for every booking event. Fully server-side; nothing is exposed to the booking frontend.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from bson import ObjectId

from app.config.database import db_config, Collections
from app.utils.helpers import serialize_doc


# ─── Calculation helpers ──────────────────────────────────────────────────────

def calculate_ticket_commission(rule: Dict, num_passengers: int) -> tuple[float, dict]:
    """Flat fee per passenger ticket."""
    ticket_fee = float(rule.get("ticket_commission", 0))
    commission_type = rule.get("ticket_commission_type", "fixed")

    if commission_type == "fixed":
        amount = ticket_fee * num_passengers
    else:
        # percentage type is not standard for tickets but handle gracefully
        amount = 0.0

    breakdown = {
        "type": "ticket",
        "fee_per_passenger": ticket_fee,
        "num_passengers": num_passengers,
        "total": amount,
    }
    return round(amount, 2), breakdown


def calculate_package_commission(rule: Dict, num_passengers: int) -> tuple[float, dict]:
    """Flat fee per package passenger."""
    pkg_fee = float(rule.get("package_commission", 0))
    commission_type = rule.get("package_commission_type", "fixed")

    if commission_type == "fixed":
        amount = pkg_fee * num_passengers
    else:
        amount = 0.0

    breakdown = {
        "type": "package",
        "fee_per_passenger": pkg_fee,
        "num_passengers": num_passengers,
        "total": amount,
    }
    return round(amount, 2), breakdown


def calculate_hotel_commission(rule: Dict, rooms_selected: List[Dict], nights: int = 1) -> tuple[float, dict]:
    """
    Per-night, per-room-type hotel commission.
    Uses the most recently valid HotelCommissionPeriod from the rule.
    """
    hotel_commissions = rule.get("hotel_commissions", [])
    if not hotel_commissions:
        return 0.0, {"type": "hotel", "total": 0.0, "lines": []}

    # Use the first period (or add date-range logic later)
    period = hotel_commissions[0] if hotel_commissions else {}

    room_type_map = {
        "sharing": "sharing_commission",
        "quint":   "quint_commission",
        "quad":    "quad_commission",
        "triple":  "triple_commission",
        "double":  "double_commission",
        "other":   "other_commission",
    }

    total = 0.0
    lines = []
    for room in rooms_selected:
        rtype = (room.get("room_type") or "sharing").lower()
        qty = int(room.get("quantity", 0) or 0)
        rate_key = room_type_map.get(rtype, "other_commission")
        nightly_rate = float(period.get(rate_key, 0))
        line_total = nightly_rate * qty * nights
        total += line_total
        lines.append({
            "room_type": rtype,
            "quantity": qty,
            "nights": nights,
            "rate_per_night": nightly_rate,
            "line_total": line_total,
        })

    breakdown = {"type": "hotel", "total": round(total, 2), "lines": lines}
    return round(total, 2), breakdown


# ─── Commission group loader ───────────────────────────────────────────────────

async def _get_commission_rule(group_id: Optional[str], expected_type: Optional[str] = None) -> Optional[Dict]:
    """Load a commission group from DB by ID, optionally verifying its categorization."""
    if not group_id:
        return None
    try:
        coll = db_config.get_collection(Collections.COMMISSIONS)
        query: Dict[str, Any] = {"_id": ObjectId(group_id)}
        if expected_type:
            query["applied_to"] = expected_type
            
        doc = await coll.find_one(query)
        if not doc and expected_type:
            # Try finding it without type check just to log a warning if it exists but type is wrong
            exists_with_wrong_type = await coll.find_one({"_id": ObjectId(group_id)})
            if exists_with_wrong_type:
                print(f"⚠️  Commission group {group_id} found but type is '{exists_with_wrong_type.get('applied_to')}', expected '{expected_type}'")
        
        return serialize_doc(doc) if doc else None
    except Exception:
        return None


async def _get_employee(employee_id: str) -> Optional[Dict]:
    coll = db_config.get_collection(Collections.EMPLOYEES)
    try:
        doc = await coll.find_one({"_id": ObjectId(employee_id)})
        return serialize_doc(doc) if doc else None
    except Exception:
        return None


async def _get_agency(agency_id: str) -> Optional[Dict]:
    coll = db_config.get_collection(Collections.AGENCIES)
    try:
        doc = await coll.find_one({"_id": ObjectId(agency_id)})
        return serialize_doc(doc) if doc else None
    except Exception:
        return None


async def _get_branch(branch_id: str) -> Optional[Dict]:
    coll = db_config.get_collection(Collections.BRANCHES)
    try:
        doc = await coll.find_one({"_id": ObjectId(branch_id)})
        return serialize_doc(doc) if doc else None
    except Exception:
        return None


# ─── Main entry-point ─────────────────────────────────────────────────────────

async def create_commission_records(
    booking: Dict,
    booking_type: str,  # "ticket" | "umrah" | "custom"
    current_user: Dict,
):
    """
    Called immediately after a booking is created.
    Determines who earns a commission, calculates amounts, and writes records.
    Silently logs and returns on any error – never blocks a booking.
    """
    try:
        role        = current_user.get("role")
        agency_type = current_user.get("agency_type")
        entity_type = current_user.get("entity_type")
        branch_id   = current_user.get("branch_id")
        agency_id   = current_user.get("agency_id") or (
            current_user.get("sub") if role == "agency" else None
        )
        employee_id = current_user.get("sub") if role == "employee" else None

        booking_id  = str(booking.get("_id", ""))
        booking_ref = booking.get("booking_reference", booking_id)
        org_id      = booking.get("organization_id") or current_user.get("organization_id")

        # Derive passenger/room counts for calculation
        passengers = booking.get("passengers") or booking.get("rooms_selected") or []
        num_passengers = len(passengers) if booking_type == "ticket" else sum(
            int(r.get("quantity", 0)) for r in (booking.get("rooms_selected") or [])
        )
        rooms_selected = booking.get("rooms_selected", [])

        # ── Determine earners ──────────────────────────────────────────────────
        earners_to_create = []  # list of (earner_type, earner_id, earner_name, group_id)

        is_branch_user   = (role == "branch") or (entity_type == "branch")
        is_employee      = (role == "employee")
        is_area_agency   = (role == "agency") and (agency_type == "area")
        is_full_agency   = (role == "agency") and (agency_type != "area")
        is_org_employee  = is_employee and (entity_type == "organization")

        if is_full_agency:
            # Full agencies are discount-based; no commission records
            return

        if is_area_agency:
            # Area Agency earns
            agency = await _get_agency(agency_id)
            if agency:
                earners_to_create.append((
                    "agency",
                    agency_id,
                    agency.get("name", "Agency"),
                    agency.get("commission_group_id"),
                ))
            # Parent Branch also earns
            if branch_id:
                branch = await _get_branch(branch_id)
                if branch:
                    earners_to_create.append((
                        "branch",
                        branch_id,
                        branch.get("name", "Branch"),
                        branch.get("commission_group_id"),
                    ))

        elif is_employee and not is_org_employee:
            # Branch Employee earns (using their group_id)
            employee = await _get_employee(employee_id)
            if employee:
                earners_to_create.append((
                    "employee",
                    employee_id,
                    employee.get("name", "Employee"),
                    employee.get("group_id"),
                ))
            # Branch also earns
            emp_branch_id = branch_id or current_user.get("entity_id") if entity_type == "branch" else None
            if emp_branch_id:
                branch = await _get_branch(emp_branch_id)
                if branch:
                    earners_to_create.append((
                        "branch",
                        emp_branch_id,
                        branch.get("name", "Branch"),
                        branch.get("commission_group_id"),
                    ))

        elif is_org_employee:
            # Org Employee earns
            employee = await _get_employee(employee_id)
            if employee:
                earners_to_create.append((
                    "employee",
                    employee_id,
                    employee.get("name", "Employee"),
                    employee.get("group_id"),
                ))

        elif is_branch_user and not is_employee:
            # Pure branch login (not employee, e.g. branch admin) - branch earns
            if branch_id:
                branch = await _get_branch(branch_id)
                if branch:
                    earners_to_create.append((
                        "branch",
                        branch_id,
                        branch.get("name", "Branch"),
                        branch.get("commission_group_id"),
                    ))

        # ── Create a record for each earner ────────────────────────────────────
        coll = db_config.get_collection(Collections.COMMISSION_RECORDS)
        now  = datetime.utcnow()

        for earner_type, earner_id, earner_name, group_id in earners_to_create:
            # Pass earner_type as expected_type to enforce categorization
            rule = await _get_commission_rule(group_id, expected_type=earner_type)
            if not rule:
                # No valid commission group for this entity type → skip silently
                continue

            # Calculate amount based on booking type
            if booking_type == "ticket":
                amount, breakdown = calculate_ticket_commission(rule, num_passengers or 1)
            elif booking_type == "umrah":
                amount, breakdown = calculate_package_commission(rule, num_passengers or 1)
            elif booking_type == "custom":
                hotel_amount, hotel_breakdown = calculate_hotel_commission(rule, rooms_selected, nights=1)
                amount, breakdown = hotel_amount, hotel_breakdown
            else:
                amount, breakdown = 0.0, {}

            record = {
                "booking_id":           booking_id,
                "booking_reference":    booking_ref,
                "booking_type":         booking_type,
                "earner_type":          earner_type,
                "earner_id":            earner_id,
                "earner_name":          earner_name,
                "organization_id":      org_id,
                "branch_id":            branch_id,
                "agency_id":            agency_id,
                "commission_amount":    amount,
                "commission_breakdown": breakdown,
                "status":               "pending",
                "trip_completion_date": None,
                "paid_at":              None,
                "paid_by":              None,
                "journal_entry_id":     None,
                "created_at":           now,
                "updated_at":           now,
            }

            await coll.insert_one(record)
            print(f"💰 Commission created: {earner_type} '{earner_name}' earns {amount} for booking {booking_ref}")

    except Exception as e:
        # Never block a booking due to commission errors
        print(f"⚠️ Commission engine warning for booking {booking.get('booking_reference','?')}: {e}")
