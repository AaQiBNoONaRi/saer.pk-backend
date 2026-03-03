"""
Discount model and schemas for pricing management
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import datetime, date

class HotelDiscountItem(BaseModel):
    quint_discount: float = 0
    quad_discount: float = 0
    triple_discount: float = 0
    double_discount: float = 0
    sharing_discount: float = 0
    other_discount: float = 0
    hotels: List[str] = []
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None

class DiscountBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    ticket_discount: float = 0
    ticket_discount_type: Literal["fixed", "percentage"] = "fixed"
    package_discount: float = 0
    package_discount_type: Literal["fixed", "percentage"] = "fixed"
    hotel_discounts: List[HotelDiscountItem] = []
    is_active: bool = True

class DiscountCreate(DiscountBase):
    pass

class DiscountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    ticket_discount: Optional[float] = None
    ticket_discount_type: Optional[Literal["fixed", "percentage"]] = None
    package_discount: Optional[float] = None
    package_discount_type: Optional[Literal["fixed", "percentage"]] = None
    hotel_discounts: Optional[List[HotelDiscountItem]] = None
    is_active: Optional[bool] = None

class DiscountResponse(DiscountBase):
    id: str = Field(alias="_id")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            date: lambda v: v.isoformat() if v else None
        }
