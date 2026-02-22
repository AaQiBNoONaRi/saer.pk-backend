"""
Pydantic models for Finance & Accounting Module
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ─── Enums ────────────────────────────────────────────────────────────────────

class AccountType(str, Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"


class EntryType(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"


class ReferenceType(str, Enum):
    UMRAH_BOOKING = "umrah_booking"
    TICKET_BOOKING = "ticket_booking"
    CUSTOM_BOOKING = "custom_booking"
    MANUAL_INCOME = "manual_income"
    MANUAL_EXPENSE = "manual_expense"
    SALARY = "salary"
    VENDOR_BILL = "vendor_bill"
    ADJUSTMENT = "adjustment"
    PAYMENT_RECEIVED = "payment_received"


class ManualEntryType(str, Enum):
    INCOME = "manual_income"
    EXPENSE = "manual_expense"
    SALARY = "salary"
    VENDOR_BILL = "vendor_bill"
    ADJUSTMENT = "adjustment"


# ─── Chart of Accounts ────────────────────────────────────────────────────────

class ChartOfAccountCreate(BaseModel):
    code: str                          # e.g. "1001"
    name: str                          # e.g. "Cash in Hand"
    type: AccountType
    parent_id: Optional[str] = None    # parent account _id
    organization_id: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True


class ChartOfAccountUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    parent_id: Optional[str] = None


# ─── Journal Entry ────────────────────────────────────────────────────────────

class JournalLine(BaseModel):
    account_id: str
    account_code: Optional[str] = None
    account_name: Optional[str] = None
    debit: float = 0.0
    credit: float = 0.0
    description: Optional[str] = None


class JournalEntryCreate(BaseModel):
    date: Optional[str] = None          # ISO date string; defaults to today
    reference_type: ReferenceType
    reference_id: Optional[str] = None
    organization_id: Optional[str] = None
    branch_id: Optional[str] = None
    agency_id: Optional[str] = None
    description: str
    entries: List[JournalLine]


class JournalEntryUpdate(BaseModel):
    description: Optional[str] = None
    entries: Optional[List[JournalLine]] = None


# ─── Manual Entry ─────────────────────────────────────────────────────────────

class ManualEntryCreate(BaseModel):
    entry_type: ManualEntryType
    date: Optional[str] = None
    description: str
    amount: float
    organization_id: Optional[str] = None
    branch_id: Optional[str] = None
    agency_id: Optional[str] = None
    # Debit / credit account overrides (optional – engine picks defaults if omitted)
    debit_account_id: Optional[str] = None
    credit_account_id: Optional[str] = None
    notes: Optional[str] = None


# ─── Report Filters ───────────────────────────────────────────────────────────

class ReportFilter(BaseModel):
    organization_id: Optional[str] = None
    branch_id: Optional[str] = None
    agency_id: Optional[str] = None
    date_from: Optional[str] = None    # YYYY-MM-DD
    date_to: Optional[str] = None      # YYYY-MM-DD


# ─── Audit Trail ──────────────────────────────────────────────────────────────

class AuditAction(str, Enum):
    CREATE_JOURNAL = "CREATE_JOURNAL"
    UPDATE_JOURNAL = "UPDATE_JOURNAL"
    DELETE_JOURNAL = "DELETE_JOURNAL"
    CREATE_COA = "CREATE_COA"
    UPDATE_COA = "UPDATE_COA"
    SEED_COA = "SEED_COA"
