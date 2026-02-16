"""
Service Charge model and schemas for fee management
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

class ServiceChargeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    applies_to: Literal["tickets", "packages", "hotels"] = "tickets"
    charge_type: Literal["fixed", "percentage"] = "fixed"
    value: float = Field(..., gt=0)
    room_type: Optional[str] = None  # For hotels: double, triple, quad, quint
    is_active: bool = True
    is_automatic: bool = False  # Auto-apply to all transactions

class ServiceChargeCreate(ServiceChargeBase):
    pass

class ServiceChargeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    applies_to: Optional[Literal["tickets", "packages", "hotels"]] = None
    charge_type: Optional[Literal["fixed", "percentage"]] = None
    value: Optional[float] = Field(None, gt=0)
    room_type: Optional[str] = None
    is_active: Optional[bool] = None
    is_automatic: Optional[bool] = None

class ServiceChargeResponse(ServiceChargeBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
