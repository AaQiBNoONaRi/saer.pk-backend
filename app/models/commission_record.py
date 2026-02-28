"""
Commission Record model – tracks the per-booking commission that each earner is owed.
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal, Dict, Any
from datetime import datetime


class CommissionRecord(BaseModel):
    """Base commission record"""
    booking_id: str
    booking_reference: str
    booking_type: Literal["ticket", "umrah", "custom"]

    # Who earns
    earner_type: Literal["employee", "agency", "branch"]
    earner_id: str
    earner_name: str

    # Hierarchy for filtering/reporting
    organization_id: Optional[str] = None
    branch_id: Optional[str] = None
    agency_id: Optional[str] = None

    # Amounts
    commission_amount: float = Field(default=0.0, ge=0)
    commission_breakdown: Dict[str, Any] = Field(default_factory=dict)

    # Lifecycle
    status: Literal["pending", "earned", "paid"] = "pending"
    trip_completion_date: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    paid_by: Optional[str] = None  # user ID who processed the payout

    # Journal reference (set upon payout)
    journal_entry_id: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CommissionRecordResponse(CommissionRecord):
    id: str = Field(alias="_id")

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MarkEarnedRequest(BaseModel):
    trip_completion_date: Optional[datetime] = None  # defaults to now


class PayoutRequest(BaseModel):
    notes: Optional[str] = None
