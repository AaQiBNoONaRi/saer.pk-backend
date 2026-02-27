"""
Finance Reports – MongoDB aggregation pipelines.

Provides:
  - Profit & Loss
  - Balance Sheet
  - Trial Balance
  - General Ledger  (organisation)
  - Agency Ledger   (filter by agency_id)
  - Branch Ledger   (filter by branch_id)

All reports use journal_entries as the single source of truth.
Ledger is derived (never stored separately).
"""
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.config.database import db_config, Collections
from app.utils.helpers import serialize_doc
from app.database.db_operations import db_ops


# ─── helpers ──────────────────────────────────────────────────────────────────

def _date_match(date_from: Optional[str], date_to: Optional[str]) -> Dict:
    if not date_from and not date_to:
        return {}
    match: Dict[str, Any] = {}
    if date_from:
        match["$gte"] = date_from
    if date_to:
        match["$lte"] = date_to + "T23:59:59"
    return {"date": match}


def _base_match(
    organization_id: Optional[str],
    branch_id: Optional[str],
    agency_id: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
) -> Dict:
    q: Dict[str, Any] = {"is_reversed": {"$ne": True}}
    if organization_id:
        q["organization_id"] = organization_id
    if branch_id:
        q["branch_id"] = branch_id
    if agency_id:
        q["agency_id"] = agency_id
    dm = _date_match(date_from, date_to)
    q.update(dm)
    return q


async def _get_account_map(organization_id: Optional[str]) -> Dict[str, Dict]:
    """Return {account_id: account_doc} for fast lookup."""
    coll  = db_config.get_collection(Collections.CHART_OF_ACCOUNTS)
    query = {"is_active": True}
    if organization_id:
        query["organization_id"] = organization_id
    docs  = await coll.find(query).to_list(length=500)
    return {str(d["_id"]): {**d, "_id": str(d["_id"])} for d in docs}


# ─── Trial Balance ─────────────────────────────────────────────────────────────

async def get_trial_balance(
    organization_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    agency_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict:
    """
    Unwind journal entry lines, group by account_id, sum debits & credits.
    Returns list of rows + totals.
    """
    coll    = db_config.get_collection(Collections.JOURNAL_ENTRIES)
    match   = _base_match(organization_id, branch_id, agency_id, date_from, date_to)
    acct_map = await _get_account_map(organization_id)

    pipeline = [
        {"$match": match},
        {"$unwind": "$entries"},
        {"$group": {
            "_id":          "$entries.account_id",
            "account_code": {"$first": "$entries.account_code"},
            "account_name": {"$first": "$entries.account_name"},
            "total_debit":  {"$sum": "$entries.debit"},
            "total_credit": {"$sum": "$entries.credit"},
        }},
        {"$addFields": {
            "balance_debit":  {"$max": [{"$subtract": ["$total_debit", "$total_credit"]}, 0]},
            "balance_credit": {"$max": [{"$subtract": ["$total_credit", "$total_debit"]}, 0]},
        }},
        {"$sort": {"account_code": 1}},
    ]

    rows = await coll.aggregate(pipeline).to_list(length=1000)

    # Enrich with account type from COA map
    enriched = []
    for row in rows:
        acct = acct_map.get(str(row.get("_id")), {})
        enriched.append({
            "account_id":     str(row.get("_id")),
            "account_code":   row.get("account_code") or acct.get("code"),
            "account_name":   row.get("account_name") or acct.get("name"),
            "account_type":   acct.get("type"),
            "total_debit":    round(row["total_debit"], 2),
            "total_credit":   round(row["total_credit"], 2),
            "balance_debit":  round(row["balance_debit"], 2),
            "balance_credit": round(row["balance_credit"], 2),
        })

    total_dr = round(sum(r["balance_debit"] for r in enriched), 2)
    total_cr = round(sum(r["balance_credit"] for r in enriched), 2)

    return {
        "rows":         enriched,
        "total_debit":  total_dr,
        "total_credit": total_cr,
        "balanced":     total_dr == total_cr,
        "generated_at": datetime.utcnow().isoformat(),
    }


# ─── Profit & Loss ─────────────────────────────────────────────────────────────

async def get_profit_and_loss(
    organization_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    agency_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict:
    tb = await get_trial_balance(organization_id, branch_id, agency_id, date_from, date_to)
    acct_map = await _get_account_map(organization_id)

    income_accounts  = [r for r in tb["rows"] if r.get("account_type") == "income"]
    expense_accounts = [r for r in tb["rows"] if r.get("account_type") == "expense"]

    # Income: credit-normal → net = credit - debit
    def _income_net(r: Dict) -> float:
        return round(r["total_credit"] - r["total_debit"], 2)

    # Expense: debit-normal → net = debit - credit
    def _expense_net(r: Dict) -> float:
        return round(r["total_debit"] - r["total_credit"], 2)

    total_income  = sum(_income_net(r)  for r in income_accounts)
    total_expense = sum(_expense_net(r) for r in expense_accounts)

    # Gross Profit = Revenue - Cost of Sales
    cos_row = next((r for r in expense_accounts if "Cost of Sales" in (r.get("account_name") or "")), None)
    cos     = _expense_net(cos_row) if cos_row else 0.0

    revenues = [r for r in income_accounts]
    revenue_total = sum(_income_net(r) for r in revenues)
    gross_profit  = round(revenue_total - cos, 2)
    net_profit    = round(total_income - total_expense, 2)

    return {
        "income": [
            {**r, "net": _income_net(r)} for r in income_accounts
        ],
        "expenses": [
            {**r, "net": _expense_net(r)} for r in expense_accounts
        ],
        "total_income":    round(total_income, 2),
        "total_expense":   round(total_expense, 2),
        "gross_profit":    gross_profit,
        "net_profit":      net_profit,
        "generated_at":    datetime.utcnow().isoformat(),
    }


# ─── Balance Sheet ─────────────────────────────────────────────────────────────

async def get_balance_sheet(
    organization_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    agency_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict:
    tb = await get_trial_balance(organization_id, branch_id, agency_id, date_from, date_to)

    def _net(r: Dict, acct_type: str) -> float:
        if acct_type == "asset":
            return round(r["total_debit"] - r["total_credit"], 2)   # debit-normal
        else:
            return round(r["total_credit"] - r["total_debit"], 2)   # credit-normal

    assets       = [r for r in tb["rows"] if r.get("account_type") == "asset"]
    liabilities  = [r for r in tb["rows"] if r.get("account_type") == "liability"]
    equities     = [r for r in tb["rows"] if r.get("account_type") == "equity"]

    pl = await get_profit_and_loss(organization_id, branch_id, agency_id, date_from, date_to)
    retained_earnings = pl["net_profit"]

    total_assets = round(sum(_net(r, "asset") for r in assets), 2)
    total_liab   = round(sum(_net(r, "liability") for r in liabilities), 2)
    total_equity = round(sum(_net(r, "equity") for r in equities) + retained_earnings, 2)

    return {
        "assets":            [{**r, "net": _net(r, "asset")}       for r in assets],
        "liabilities":       [{**r, "net": _net(r, "liability")}   for r in liabilities],
        "equity":            [{**r, "net": _net(r, "equity")}      for r in equities],
        "total_assets":      total_assets,
        "total_liabilities": total_liab,
        "total_equity":      total_equity,
        "retained_earnings": retained_earnings,
        "balanced":          round(total_assets, 2) == round(total_liab + total_equity, 2),
        "generated_at":      datetime.utcnow().isoformat(),
    }


# ─── General / Agency / Branch Ledger ─────────────────────────────────────────

async def get_ledger(
    organization_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    agency_id: Optional[str] = None,
    account_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Dict:
    """
    General Ledger view.
    If account_id given → single account ledger with running balance.
    Otherwise → summary per account.
    """
    coll  = db_config.get_collection(Collections.JOURNAL_ENTRIES)
    match = _base_match(organization_id, branch_id, agency_id, date_from, date_to)

    if account_id:
        # Fetch all lines for that account ordered by date
        pipeline = [
            {"$match": match},
            {"$unwind": "$entries"},
            {"$match": {"entries.account_id": account_id}},
            {"$sort": {"date": 1, "created_at": 1}},
            {"$skip": skip},
            {"$limit": limit},
            {"$project": {
                "date":           1,
                "reference_type": 1,
                "reference_id":   1,
                "description":    1,
                "entry_desc":     "$entries.description",
                "debit":          "$entries.debit",
                "credit":         "$entries.credit",
            }},
        ]
        rows = await coll.aggregate(pipeline).to_list(length=limit)

        # Running balance
        balance = 0.0
        enriched = []
        for r in rows:
            balance += float(r.get("debit", 0)) - float(r.get("credit", 0))
            enriched.append({
                "date":           r.get("date"),
                "reference_type": r.get("reference_type"),
                "reference_id":   r.get("reference_id"),
                "description":    r.get("description"),
                "entry_desc":     r.get("entry_desc"),
                "debit":          round(float(r.get("debit", 0)), 2),
                "credit":         round(float(r.get("credit", 0)), 2),
                "balance":        round(balance, 2),
            })

        return {"account_id": account_id, "rows": enriched, "generated_at": datetime.utcnow().isoformat()}

    else:
        # Summary ledger (Trial Balance style but with all cols)
        tb = await get_trial_balance(organization_id, branch_id, agency_id, date_from, date_to)
        return {"rows": tb["rows"], "generated_at": datetime.utcnow().isoformat()}


# ─── Agency Statement (agency's own perspective) ───────────────────────────────

async def get_agency_statement(
    agency_id: str,
    organization_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 200,
) -> Dict:
    """
    All journal entries scoped to this agency, from the agency perspective:
      - booking journals   → amount billed (shown as 'Amount Owed')
      - payment_received   → amount paid   (shown as 'Amount Paid')
    Balance starts at 0; bookings add to it; payments reduce it.
    A positive running_balance means the agency still owes that amount.
    """
    coll = db_config.get_collection(Collections.JOURNAL_ENTRIES)
    match: Dict = {"is_reversed": {"$ne": True}, "agency_id": agency_id}
    if organization_id:
        match["organization_id"] = organization_id
    dm = _date_match(date_from, date_to)
    match.update(dm)

    pipeline = [
        {"$match": match},
        {"$sort": {"date": 1, "created_at": 1}},
        {"$limit": limit},
        {"$project": {
            "date": 1,
            "reference_type": 1,
            "reference_id": 1,
            "description": 1,
            "entries": 1,
        }},
    ]
    docs = await coll.aggregate(pipeline).to_list(length=limit)

    rows = []
    running_balance = 0.0

    for doc in docs:
        ref_type = doc.get("reference_type", "")
        ref_id   = doc.get("reference_id", "")
        desc     = doc.get("description", "")
        date_val = doc.get("date", "")
        entries  = doc.get("entries", [])

        if ref_type in ("ticket_booking", "umrah_booking", "custom_booking"):
            # Only consider the RECEIVABLE side of booking journals.
            # The cost-of-sales journal for the same ref_id has no Receivable entry,
            # so this filter naturally skips it.
            receivable_entries = [
                e for e in entries
                if float(e.get("debit", 0)) > 0
                and "receivable" in (e.get("account_name") or e.get("description") or "").lower()
            ]
            if not receivable_entries:
                continue  # skip cost-of-sales and other companion journals

            amount = sum(float(e.get("debit", 0)) for e in receivable_entries)
            # Balance goes NEGATIVE: agency owes this amount to the organization
            running_balance -= amount
            rows.append({
                "date": date_val,
                "reference_type": ref_type,
                "reference_id": ref_id,
                "description": desc,
                "entry_desc": receivable_entries[0].get("description", desc),
                "amount_owed": round(amount, 2),
                "amount_paid": 0.0,
                "balance": round(running_balance, 2),
            })

        elif ref_type == "payment_received":
            # Payment by agency — reduces what they owe (balance goes toward 0 / positive)
            amount = sum(float(e.get("credit", 0)) for e in entries if float(e.get("credit", 0)) > 0)
            if amount:
                running_balance += amount
                rows.append({
                    "date": date_val,
                    "reference_type": ref_type,
                    "reference_id": ref_id,
                    "description": desc,
                    "entry_desc": next(
                        (e.get("description") for e in entries if float(e.get("credit", 0)) > 0),
                        desc
                    ),
                    "amount_owed": 0.0,
                    "amount_paid": round(amount, 2),
                    "balance": round(running_balance, 2),
                })


    return {
        "agency_id": agency_id,
        "total_owed": round(sum(r["amount_owed"] for r in rows), 2),
        "total_paid": round(sum(r["amount_paid"] for r in rows), 2),
        "current_balance": round(running_balance, 2),
        "rows": rows,
        "generated_at": datetime.utcnow().isoformat(),
    }


async def get_all_agency_statements(
    organization_id: Optional[str] = None,
    branch_id: Optional[str] = None
) -> List[Dict]:
    """
    Get a summary of all agency balances (receivables) for the organization.
    Only returns agencies that have a negative balance (org is owed money).
    Discovers agencies from journal entries directly to avoid ID type mismatches.
    """
    from bson import ObjectId

    coll = db_config.get_collection(Collections.JOURNAL_ENTRIES)

    # Step 1: Find all unique agency_ids from journal entries for this organization
    match: Dict = {
        "is_reversed": {"$ne": True},
        "agency_id": {"$exists": True, "$ne": None, "$ne": ""},
    }
    if organization_id:
        match["organization_id"] = organization_id

    pipeline = [
        {"$match": match},
        {"$group": {"_id": "$agency_id"}},
    ]
    agency_id_docs = await coll.aggregate(pipeline).to_list(length=500)
    agency_ids = [doc["_id"] for doc in agency_id_docs if doc.get("_id")]

    if not agency_ids:
        return []

    # Step 2: Look up agency details in bulk
    try:
        object_ids = [ObjectId(aid) for aid in agency_ids if aid]
        agency_docs = await db_ops.get_all(Collections.AGENCIES, {"_id": {"$in": object_ids}})
    except Exception:
        agency_docs = []

    agency_map = {str(a["_id"]): a for a in agency_docs}

    # Step 3: Compute balance for each agency using existing logic
    statements = []
    for agency_id in agency_ids:
        try:
            statement = await get_agency_statement(
                agency_id=agency_id,
                organization_id=organization_id,
            )
        except Exception:
            continue

        # current_balance < 0 means the agency owes money to the org
        if statement["current_balance"] < 0:
            agency_info = agency_map.get(agency_id, {})
            statements.append({
                "agency_id": agency_id,
                "agency_name": agency_info.get("name") or agency_info.get("agency_name") or agency_id,
                "email": agency_info.get("email"),
                "phone": agency_info.get("phone"),
                "total_owed": statement["total_owed"],
                "total_paid": statement["total_paid"],
                "current_balance": statement["current_balance"],
            })

    # Sort by most negative first (largest debt first)
    statements.sort(key=lambda x: x["current_balance"])
    return statements


# ─── Dashboard KPIs ────────────────────────────────────────────────────────────

async def get_dashboard_kpis(
    organization_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    agency_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict:
    pl = await get_profit_and_loss(organization_id, branch_id, agency_id, date_from, date_to)
    tb = await get_trial_balance(organization_id, branch_id, agency_id, date_from, date_to)

    def _balance_by_name(tb_rows: List[Dict], name_fragment: str, acct_type: str) -> float:
        for r in tb_rows:
            if name_fragment.lower() in (r.get("account_name") or "").lower():
                if acct_type == "asset":
                    return round(r["total_debit"] - r["total_credit"], 2)
                else:
                    return round(r["total_credit"] - r["total_debit"], 2)
        return 0.0

    ar  = _balance_by_name(tb["rows"], "Accounts Receivable", "asset")
    ap  = _balance_by_name(tb["rows"], "Supplier Payable",    "liability")

    return {
        "revenue":                  pl["total_income"],
        "gross_profit":             pl["gross_profit"],
        "net_profit":               pl["net_profit"],
        "outstanding_receivables":  ar,
        "outstanding_payables":     ap,
        "generated_at":             datetime.utcnow().isoformat(),
    }
