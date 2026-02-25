"""
Journal Engine – Core double-entry accounting logic.

Every financial event (booking creation, payment, manual entry) calls into
this module.  A journal entry is ONLY valid when:
    sum(debit lines) == sum(credit lines)
"""
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from bson import ObjectId

from app.config.database import db_config, Collections
from app.utils.helpers import serialize_doc


# ─── helpers ──────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.utcnow().isoformat()


async def _resolve_account(organization_id: Optional[str], name_fragment: str) -> Optional[Dict]:
    """Find a COA account by partial name match within an organisation."""
    coll = db_config.get_collection(Collections.CHART_OF_ACCOUNTS)
    query: Dict[str, Any] = {"name": {"$regex": name_fragment, "$options": "i"}, "is_active": True}
    if organization_id:
        query["organization_id"] = organization_id
    doc = await coll.find_one(query)
    return serialize_doc(doc) if doc else None


async def _get_account_by_code(organization_id: Optional[str], code: str) -> Optional[Dict]:
    coll = db_config.get_collection(Collections.CHART_OF_ACCOUNTS)
    query: Dict[str, Any] = {"code": code, "is_active": True}
    if organization_id:
        query["organization_id"] = organization_id
    doc = await coll.find_one(query)
    return serialize_doc(doc) if doc else None


# ─── validation ───────────────────────────────────────────────────────────────

def validate_double_entry(entries: List[Dict]) -> bool:
    """Strict double-entry: total debits must equal total credits."""
    total_debit = sum(float(e.get("debit", 0)) for e in entries)
    total_credit = sum(float(e.get("credit", 0)) for e in entries)
    return round(total_debit, 2) == round(total_credit, 2)


# ─── audit trail ──────────────────────────────────────────────────────────────

async def write_audit(
    action: str,
    collection: str,
    reference_id: str,
    old_data: Optional[Dict],
    new_data: Optional[Dict],
    performed_by: str,
):
    coll = db_config.get_collection(Collections.AUDIT_TRAIL)
    await coll.insert_one({
        "action": action,
        "collection": collection,
        "reference_id": reference_id,
        "old_data": old_data or {},
        "new_data": new_data or {},
        "performed_by": performed_by,
        "timestamp": datetime.utcnow(),
    })


# ─── low-level journal creation ───────────────────────────────────────────────

async def create_journal_entry(
    reference_type: str,
    reference_id: str,
    description: str,
    entries: List[Dict],
    organization_id: Optional[str],
    branch_id: Optional[str],
    agency_id: Optional[str],
    created_by: str,
    date_str: Optional[str] = None,
) -> Dict:
    """
    Persist a validated journal entry.  Raises ValueError if debits ≠ credits.
    """
    if not validate_double_entry(entries):
        total_dr = sum(float(e.get("debit", 0)) for e in entries)
        total_cr = sum(float(e.get("credit", 0)) for e in entries)
        raise ValueError(
            f"Double-entry violation: debits={total_dr} != credits={total_cr}"
        )

    entry_date = date_str or _now_iso()

    doc = {
        "date": entry_date,
        "reference_type": reference_type,
        "reference_id": reference_id,
        "organization_id": organization_id,
        "branch_id": branch_id,
        "agency_id": agency_id,
        "description": description,
        "entries": entries,
        "created_by": created_by,
        "created_at": datetime.utcnow(),
        "is_reversed": False,
    }

    coll = db_config.get_collection(Collections.JOURNAL_ENTRIES)
    result = await coll.insert_one(doc)
    doc["_id"] = str(result.inserted_id)

    await write_audit(
        action="CREATE_JOURNAL",
        collection=Collections.JOURNAL_ENTRIES,
        reference_id=str(result.inserted_id),
        old_data=None,
        new_data=doc,
        performed_by=created_by,
    )
    return doc


# ─── Umrah booking journal ─────────────────────────────────────────────────────

async def create_umrah_booking_journal(
    booking: Dict,
    organization_id: Optional[str],
    branch_id: Optional[str],
    agency_id: Optional[str],
    created_by: str,
):
    """
    Auto journal for an Umrah package booking:

    DR  Accounts Receivable (Agency)      selling_total
    CR  Umrah Revenue                     selling_total

    DR  Cost of Sales                     purchasing_total
    CR  Supplier Payable                  purchasing_total
    """
    # derive selling and purchasing totals for P&L
    selling_total, purchasing_total = _calculate_booking_pnl(booking)

    # ── resolve account objects ──────────────────────────────────────────────
    ar_acct   = await _resolve_account(organization_id, "Accounts Receivable")
    rev_acct  = await _resolve_account(organization_id, "Umrah Revenue")
    cos_acct  = await _resolve_account(organization_id, "Cost of Sales")
    sup_acct  = await _resolve_account(organization_id, "Supplier Payable")

    if not all([ar_acct, rev_acct, cos_acct, sup_acct]):
        missing = [
            name for name, acct in [
                ("Accounts Receivable", ar_acct),
                ("Umrah Revenue", rev_acct),
                ("Cost of Sales", cos_acct),
                ("Supplier Payable", sup_acct),
            ] if not acct
        ]
        raise ValueError(
            f"Missing COA accounts for journal engine: {missing}. "
            "Please seed the Chart of Accounts first."
        )

    agency_name = (booking.get("agency_details") or {}).get("name", "Agency")
    ref         = booking.get("booking_reference", "")

    # ── Journal 1: Revenue side ──────────────────────────────────────────────
    revenue_entries = [
        {
            "account_id":   ar_acct["_id"],
            "account_code": ar_acct.get("code"),
            "account_name": ar_acct.get("name"),
            "debit":        selling_total,
            "credit":       0.0,
            "description":  f"Receivable – {agency_name}",
        },
        {
            "account_id":   rev_acct["_id"],
            "account_code": rev_acct.get("code"),
            "account_name": rev_acct.get("name"),
            "debit":        0.0,
            "credit":       selling_total,
            "description":  f"Umrah Revenue – {ref}",
        },
    ]

    await create_journal_entry(
        reference_type="umrah_booking",
        reference_id=ref,
        description=f"Umrah booking – {agency_name} – {ref}",
        entries=revenue_entries,
        organization_id=organization_id,
        branch_id=branch_id,
        agency_id=agency_id,
        created_by=created_by,
    )

    # ── Journal 2: Cost side ─────────────────────────────────────────────────
    if purchasing_total > 0:
        cost_entries = [
            {
                "account_id":   cos_acct["_id"],
                "account_code": cos_acct.get("code"),
                "account_name": cos_acct.get("name"),
                "debit":        purchasing_total,
                "credit":       0.0,
                "description":  f"Cost of Sales – {ref}",
            },
            {
                "account_id":   sup_acct["_id"],
                "account_code": sup_acct.get("code"),
                "account_name": sup_acct.get("name"),
                "debit":        0.0,
                "credit":       purchasing_total,
                "description":  f"Supplier Payable – {ref}",
            },
        ]
        await create_journal_entry(
            reference_type="umrah_booking",
            reference_id=ref,
            description=f"Cost of Sales – {agency_name} – {ref}",
            entries=cost_entries,
            organization_id=organization_id,
            branch_id=branch_id,
            agency_id=agency_id,
            created_by=created_by,
        )


def _calculate_purchasing_total(booking: Dict) -> float:
    """
    Derive purchasing total from package_details pricing or rooms_selected.
    Priority:
    1. booking.purchasing_total (if stored explicitly)
    2. rooms_selected × purchasing price per person
    3. 0 (fallback – will skip cost journal)
    """
    # 1. Explicit field
    if booking.get("purchasing_total"):
        return float(booking["purchasing_total"])

    # 2. Derive from rooms_selected using package_details pricing
    rooms = booking.get("rooms_selected") or []
    pkg   = booking.get("package_details") or {}
    prices = pkg.get("prices") or pkg.get("room_prices") or {}

    total = 0.0
    for room in rooms:
        room_type  = room.get("room_type", "")
        quantity   = int(room.get("quantity", 0))
        # Try purchasing_price_per_person from package, else fall back to 0
        ppp = (
            (prices.get(room_type) or {}).get("purchasing_price_per_person")
            or (prices.get(room_type) or {}).get("purchase_price")
            or 0
        )
        total += float(ppp) * quantity

    return total


def _calculate_booking_pnl(booking: Dict) -> (float, float):
    """
    Derive selling total and purchasing total from a booking payload.

    Rules (best-effort using available booking structure):
    - selling_total: taken from `booking.total_amount` when present
    - purchasing_total: sum of any explicit purchasing fields found in
      package_details (food.purchasing, transport.purchasing, ziyarats.purchasing,
      visa_pricing.*_purchasing), plus room-level purchasing prices if available

    Returns: (selling_total, purchasing_total)
    """
    selling_total = float(booking.get("total_amount", 0))

    pkg = booking.get("package_details") or {}
    purchasing = 0.0

    # package-level components
    for comp in ("food", "ziyarat", "transport"):
        v = pkg.get(comp) or {}
        if isinstance(v, dict) and v.get("purchasing"):
            try:
                purchasing += float(v.get("purchasing", 0))
            except Exception:
                pass

    # visa per passenger
    visa = pkg.get("visa_pricing") or {}
    if visa:
        for p in booking.get("passengers", []) or []:
            ptype = (p.get("type") or "adult").lower()
            key = f"{ptype}_purchasing"
            if visa.get(key) is not None:
                try:
                    purchasing += float(visa.get(key, 0))
                except Exception:
                    pass

    # rooms_selected: try several places for purchasing price
    rooms = booking.get("rooms_selected") or []
    prices = pkg.get("prices") or pkg.get("room_prices") or pkg.get("package_prices") or {}
    for room in rooms:
        qty = int(room.get("quantity", 0) or 0)
        # room-level explicit purchasing price
        ppp = room.get("purchasing_price_per_person") or room.get("purchase_price") or room.get("price_per_person")
        if ppp is None:
            # try package-level mapping
            try:
                rtype = room.get("room_type")
                pack_info = (prices.get(rtype) or {}) if isinstance(prices, dict) else {}
                ppp = pack_info.get("purchasing_price_per_person") or pack_info.get("purchase_price")
            except Exception:
                ppp = None
        try:
            ppp_val = float(ppp or 0)
        except Exception:
            ppp_val = 0.0
        purchasing += ppp_val * qty

    # As a last step, include any explicit top-level purchasing_total if present
    if booking.get("purchasing_total"):
        try:
            purchasing = float(booking.get("purchasing_total"))
        except Exception:
            pass

    return selling_total, purchasing


# ─── Payment received journal ──────────────────────────────────────────────────

async def create_payment_received_journal(
    booking_reference: str,
    amount: float,
    payment_method: str,           # "cash" | "bank" | "online"
    agency_name: str,
    organization_id: Optional[str],
    branch_id: Optional[str],
    agency_id: Optional[str],
    created_by: str,
):
    """
    DR  Cash / Bank          amount
    CR  Accounts Receivable  amount
    """
    bank_name = "Bank" if payment_method in ("bank", "online", "transfer") else "Cash in Hand"
    cash_acct = await _resolve_account(organization_id, bank_name)
    ar_acct   = await _resolve_account(organization_id, "Accounts Receivable")

    if not all([cash_acct, ar_acct]):
        raise ValueError("Missing Cash/Bank or Accounts Receivable in COA.")

    entries = [
        {
            "account_id":   cash_acct["_id"],
            "account_code": cash_acct.get("code"),
            "account_name": cash_acct.get("name"),
            "debit":        amount,
            "credit":       0.0,
            "description":  f"Payment received – {agency_name}",
        },
        {
            "account_id":   ar_acct["_id"],
            "account_code": ar_acct.get("code"),
            "account_name": ar_acct.get("name"),
            "debit":        0.0,
            "credit":       amount,
            "description":  f"Receivable settled – {booking_reference}",
        },
    ]

    return await create_journal_entry(
        reference_type="payment_received",
        reference_id=booking_reference,
        description=f"Payment received – {agency_name} – {booking_reference}",
        entries=entries,
        organization_id=organization_id,
        branch_id=branch_id,
        agency_id=agency_id,
        created_by=created_by,
    )
