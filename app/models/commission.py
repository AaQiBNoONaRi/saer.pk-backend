"""
Commission model and schemas for partner earnings management
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, date

class CommissionBase(BaseModel):
    partner_name: str = Field(..., min_length=1, max_length=200)
    partner_type: Literal["hotel", "agency", "transport"] = "hotel"
    description: Optional[str] = None
    commission_type: Literal["fixed", "per_night"] = "fixed"
    value: float = Field(..., gt=0)
    status: Literal["pending", "earned", "paid"] = "pending"
    related_booking_id: Optional[str] = None
    earned_date: Optional[date] = None
    paid_date: Optional[date] = None
    payment_notes: Optional[str] = None

class CommissionCreate(CommissionBase):
    pass

class CommissionUpdate(BaseModel):
    partner_name: Optional[str] = Field(None, min_length=1, max_length=200)
    partner_type: Optional[Literal["hotel", "agency", "transport"]] = None
    description: Optional[str] = None
    commission_type: Optional[Literal["fixed", "per_night"]] = None
    value: Optional[float] = Field(None, gt=0)
    status: Optional[Literal["pending", "earned", "paid"]] = None
    related_booking_id: Optional[str] = None
    earned_date: Optional[date] = None
    paid_date: Optional[date] = None
    payment_notes: Optional[str] = None

class CommissionResponse(CommissionBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }
