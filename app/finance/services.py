"""
Finance Services – Business logic for Chart of Accounts, Journal Entries,
Manual Entries and Audit Trail.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId

from app.config.database import db_config, Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.finance.journal_engine import (
    create_journal_entry,
    write_audit,
    validate_double_entry,
)
from app.finance.models import ManualEntryType


# ─── Chart of Accounts ────────────────────────────────────────────────────────

async def create_account(data: Dict, created_by: str) -> Dict:
    coll = db_config.get_collection(Collections.CHART_OF_ACCOUNTS)
    existing = await coll.find_one({
        "code": data["code"],
        "organization_id": data.get("organization_id"),
    })
    if existing:
        raise ValueError(f"Account code '{data['code']}' already exists.")
    data["created_by"] = created_by
    data["created_at"] = datetime.utcnow()
    result = await coll.insert_one(data)
    doc = await coll.find_one({"_id": result.inserted_id})
    created = serialize_doc(doc)
    await write_audit("CREATE_COA", Collections.CHART_OF_ACCOUNTS,
                      str(result.inserted_id), None, created, created_by)
    return created


async def get_accounts(
    organization_id: Optional[str] = None,
    account_type: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> List[Dict]:
    coll = db_config.get_collection(Collections.CHART_OF_ACCOUNTS)
    query: Dict[str, Any] = {}
    if organization_id:
        query["organization_id"] = organization_id
    if account_type:
        query["type"] = account_type
    if is_active is not None:
        query["is_active"] = is_active
    cursor = coll.find(query).sort("code", 1)
    docs = await cursor.to_list(length=500)
    return serialize_docs(docs)


async def update_account(account_id: str, data: Dict, updated_by: str) -> Dict:
    coll = db_config.get_collection(Collections.CHART_OF_ACCOUNTS)
    old_doc = await coll.find_one({"_id": ObjectId(account_id)})
    if not old_doc:
        raise ValueError(f"Account {account_id} not found.")
    old = serialize_doc(old_doc)
    data["updated_by"] = updated_by
    data["updated_at"] = datetime.utcnow()
    await coll.update_one({"_id": ObjectId(account_id)}, {"$set": data})
    new_doc = await coll.find_one({"_id": ObjectId(account_id)})
    new = serialize_doc(new_doc)
    await write_audit("UPDATE_COA", Collections.CHART_OF_ACCOUNTS,
                      account_id, old, new, updated_by)
    return new


# ─── Seed default Chart of Accounts ──────────────────────────────────────────

DEFAULT_COA = [
    # Assets
    {"code": "1000", "name": "Assets",              "type": "asset",     "parent": None},
    {"code": "1001", "name": "Cash in Hand",         "type": "asset",     "parent": "1000"},
    {"code": "1002", "name": "Bank Account",         "type": "asset",     "parent": "1000"},
    {"code": "1003", "name": "Accounts Receivable",  "type": "asset",     "parent": "1000"},
    {"code": "1004", "name": "Advance to Supplier",  "type": "asset",     "parent": "1000"},
    # Liabilities
    {"code": "2000", "name": "Liabilities",          "type": "liability", "parent": None},
    {"code": "2001", "name": "Supplier Payable",     "type": "liability", "parent": "2000"},
    {"code": "2002", "name": "Agency Deposits",      "type": "liability", "parent": "2000"},
    {"code": "2003", "name": "Salary Payable",       "type": "liability", "parent": "2000"},
    # Equity
    {"code": "3000", "name": "Equity",               "type": "equity",    "parent": None},
    {"code": "3001", "name": "Capital",              "type": "equity",    "parent": "3000"},
    {"code": "3002", "name": "Retained Earnings",    "type": "equity",    "parent": "3000"},
    # Income
    {"code": "4000", "name": "Income",               "type": "income",    "parent": None},
    {"code": "4001", "name": "Umrah Revenue",        "type": "income",    "parent": "4000"},
    {"code": "4002", "name": "Ticket Revenue",       "type": "income",    "parent": "4000"},
    {"code": "4003", "name": "Visa Revenue",         "type": "income",    "parent": "4000"},
    {"code": "4004", "name": "Service Charges",      "type": "income",    "parent": "4000"},
    # Expenses
    {"code": "5000", "name": "Expenses",             "type": "expense",   "parent": None},
    {"code": "5001", "name": "Cost of Sales",        "type": "expense",   "parent": "5000"},
    {"code": "5002", "name": "Salary Expense",       "type": "expense",   "parent": "5000"},
    {"code": "5003", "name": "Rent",                 "type": "expense",   "parent": "5000"},
    {"code": "5004", "name": "Utilities",            "type": "expense",   "parent": "5000"},
    {"code": "5005", "name": "Marketing",            "type": "expense",   "parent": "5000"},
]


async def seed_chart_of_accounts(organization_id: str, seeded_by: str) -> Dict:
    """Insert default COA for an organisation (idempotent by code)."""
    coll = db_config.get_collection(Collections.CHART_OF_ACCOUNTS)
    inserted = 0
    skipped  = 0
    code_to_id: Dict[str, str] = {}

    # First pass – insert parent accounts (parent == None)
    for acct in DEFAULT_COA:
        if acct["parent"] is None:
            existing = await coll.find_one({"code": acct["code"], "organization_id": organization_id})
            if existing:
                code_to_id[acct["code"]] = str(existing["_id"])
                skipped += 1
                continue
            doc = {
                "code": acct["code"],
                "name": acct["name"],
                "type": acct["type"],
                "parent_id": None,
                "organization_id": organization_id,
                "is_active": True,
                "created_by": seeded_by,
                "created_at": datetime.utcnow(),
            }
            result = await coll.insert_one(doc)
            code_to_id[acct["code"]] = str(result.inserted_id)
            inserted += 1

    # Second pass – insert child accounts
    for acct in DEFAULT_COA:
        if acct["parent"] is not None:
            existing = await coll.find_one({"code": acct["code"], "organization_id": organization_id})
            if existing:
                code_to_id[acct["code"]] = str(existing["_id"])
                skipped += 1
                continue
            parent_oid = code_to_id.get(acct["parent"])
            doc = {
                "code": acct["code"],
                "name": acct["name"],
                "type": acct["type"],
                "parent_id": parent_oid,
                "organization_id": organization_id,
                "is_active": True,
                "created_by": seeded_by,
                "created_at": datetime.utcnow(),
            }
            result = await coll.insert_one(doc)
            code_to_id[acct["code"]] = str(result.inserted_id)
            inserted += 1

    await write_audit(
        "SEED_COA", Collections.CHART_OF_ACCOUNTS, organization_id,
        None, {"inserted": inserted, "skipped": skipped}, seeded_by
    )
    return {"inserted": inserted, "skipped": skipped}


# ─── Manual Journal Entries ───────────────────────────────────────────────────

# Default account mappings per manual entry type (code-based)
_MANUAL_DEFAULTS: Dict[str, Dict[str, str]] = {
    ManualEntryType.INCOME:      {"debit": "1001", "credit": "4001"},  # Cash / Income
    ManualEntryType.EXPENSE:     {"debit": "5005", "credit": "1001"},  # Expense / Cash
    ManualEntryType.SALARY:      {"debit": "5002", "credit": "2003"},  # Salary Exp / Salary Payable
    ManualEntryType.VENDOR_BILL: {"debit": "5001", "credit": "2001"},  # CoS / Supplier Payable
    ManualEntryType.ADJUSTMENT:  {"debit": "3002", "credit": "3002"},  # Retained Earnings (symmetric)
}


async def _get_account_by_code_in_org(org_id: Optional[str], code: str) -> Optional[Dict]:
    coll = db_config.get_collection(Collections.CHART_OF_ACCOUNTS)
    q: Dict[str, Any] = {"code": code, "is_active": True}
    if org_id:
        q["organization_id"] = org_id
    doc = await coll.find_one(q)
    return serialize_doc(doc) if doc else None


async def create_manual_entry(data: Dict, created_by: str) -> Dict:
    org_id     = data.get("organization_id")
    entry_type = data.get("entry_type")
    amount     = float(data.get("amount", 0))
    description = data.get("description", "Manual entry")
    date_str    = data.get("date")

    defaults = _MANUAL_DEFAULTS.get(entry_type, {"debit": "1001", "credit": "4001"})

    # Resolve debit account
    dr_id = data.get("debit_account_id")
    if dr_id:
        coll = db_config.get_collection(Collections.CHART_OF_ACCOUNTS)
        dr_doc = serialize_doc(await coll.find_one({"_id": ObjectId(dr_id)}))
    else:
        dr_doc = await _get_account_by_code_in_org(org_id, defaults["debit"])

    # Resolve credit account
    cr_id = data.get("credit_account_id")
    if cr_id:
        coll = db_config.get_collection(Collections.CHART_OF_ACCOUNTS)
        cr_doc = serialize_doc(await coll.find_one({"_id": ObjectId(cr_id)}))
    else:
        cr_doc = await _get_account_by_code_in_org(org_id, defaults["credit"])

    if not dr_doc or not cr_doc:
        raise ValueError("Could not resolve debit or credit account. Seed COA first.")

    entries = [
        {
            "account_id":   dr_doc["_id"],
            "account_code": dr_doc.get("code"),
            "account_name": dr_doc.get("name"),
            "debit":        amount,
            "credit":       0.0,
            "description":  description,
        },
        {
            "account_id":   cr_doc["_id"],
            "account_code": cr_doc.get("code"),
            "account_name": cr_doc.get("name"),
            "debit":        0.0,
            "credit":       amount,
            "description":  description,
        },
    ]

    return await create_journal_entry(
        reference_type=entry_type,
        reference_id=f"MANUAL-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        description=description,
        entries=entries,
        organization_id=org_id,
        branch_id=data.get("branch_id"),
        agency_id=data.get("agency_id"),
        created_by=created_by,
        date_str=date_str,
    )


# ─── Journal Entry CRUD ───────────────────────────────────────────────────────

async def get_journal_entries(
    organization_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    agency_id: Optional[str] = None,
    reference_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[Dict]:
    coll = db_config.get_collection(Collections.JOURNAL_ENTRIES)
    query: Dict[str, Any] = {}
    if organization_id:
        query["organization_id"] = organization_id
    if branch_id:
        query["branch_id"] = branch_id
    if agency_id:
        query["agency_id"] = agency_id
    if reference_type:
        query["reference_type"] = reference_type
    if date_from or date_to:
        query["date"] = {}
        if date_from:
            query["date"]["$gte"] = date_from
        if date_to:
            query["date"]["$lte"] = date_to + "T23:59:59"
    cursor = coll.find(query).sort("created_at", -1).skip(skip).limit(limit)
    return serialize_docs(await cursor.to_list(length=limit))


async def get_journal_entry(entry_id: str) -> Optional[Dict]:
    coll = db_config.get_collection(Collections.JOURNAL_ENTRIES)
    doc = await coll.find_one({"_id": ObjectId(entry_id)})
    return serialize_doc(doc) if doc else None


async def delete_journal_entry(entry_id: str, deleted_by: str) -> Dict:
    """Soft-delete (mark is_reversed=True) to preserve audit history."""
    coll = db_config.get_collection(Collections.JOURNAL_ENTRIES)
    doc = await coll.find_one({"_id": ObjectId(entry_id)})
    if not doc:
        raise ValueError(f"Journal entry {entry_id} not found.")
    old = serialize_doc(doc)
    await coll.update_one({"_id": ObjectId(entry_id)}, {"$set": {"is_reversed": True, "reversed_by": deleted_by}})
    new = serialize_doc(await coll.find_one({"_id": ObjectId(entry_id)}))
    await write_audit("DELETE_JOURNAL", Collections.JOURNAL_ENTRIES, entry_id, old, new, deleted_by)
    return new


# ─── Audit Trail ──────────────────────────────────────────────────────────────

async def get_audit_trail(
    organization_id: Optional[str] = None,
    action: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[Dict]:
    coll = db_config.get_collection(Collections.AUDIT_TRAIL)
    query: Dict[str, Any] = {}
    if action:
        query["action"] = action
    # Audit trail doesn't have org_id but reference_id can be org scoped via join –
    # keep it simple and return unfiltered for now (UI filters client side)
    cursor = coll.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    return serialize_docs(await cursor.to_list(length=limit))
