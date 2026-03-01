"""
Discount model and schemas for pricing management
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, date

class DiscountBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    discount_type: Literal["fixed", "percentage"] = "fixed"
    value: float = Field(..., gt=0)
    applies_to: Literal["tickets", "packages", "hotels"] = "tickets"
    room_type: Optional[str] = None  # For hotels: double, triple, quad, quint
    is_active: bool = True
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None

class DiscountCreate(DiscountBase):
    pass

class DiscountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    discount_type: Optional[Literal["fixed", "percentage"]] = None
    value: Optional[float] = Field(None, gt=0)
    applies_to: Optional[Literal["tickets", "packages", "hotels"]] = None
    room_type: Optional[str] = None
    is_active: Optional[bool] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None

class DiscountResponse(DiscountBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }
