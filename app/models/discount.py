"""  
Discount model and schemas for pricing management
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime, date

class HotelDiscountPeriod(BaseModel):
    """Hotel discount period with room-specific discounts"""
    quint_discount: float = Field(default=0, ge=0)
    quad_discount: float = Field(default=0, ge=0)
    triple_discount: float = Field(default=0, ge=0)
    double_discount: float = Field(default=0, ge=0)
    sharing_discount: float = Field(default=0, ge=0)
    other_discount: float = Field(default=0, ge=0)
    hotels: List[str] = Field(default_factory=list)  # List of hotel IDs
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None

class DiscountBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Discount group name")
    ticket_discount: float = Field(default=0, ge=0, description="Group ticket discount amount")
    ticket_discount_type: Literal["percentage", "fixed"] = Field(default="fixed", description="Discount type for tickets")
    package_discount: float = Field(default=0, ge=0, description="Umrah package discount amount")
    package_discount_type: Literal["percentage", "fixed"] = Field(default="fixed", description="Discount type for packages")
    hotel_discounts: List[HotelDiscountPeriod] = Field(default_factory=list, description="Hotel discount periods")
    is_active: bool = True
    
    @field_validator('ticket_discount')
    @classmethod
    def validate_ticket_discount(cls, v, info):
        if info.data.get('ticket_discount_type') == 'percentage' and v > 100:
            raise ValueError('Percentage discount cannot exceed 100%')
        return v
    
    @field_validator('package_discount')
    @classmethod
    def validate_package_discount(cls, v, info):
        if info.data.get('package_discount_type') == 'percentage' and v > 100:
            raise ValueError('Percentage discount cannot exceed 100%')
        return v

class DiscountCreate(DiscountBase):
    pass

class DiscountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    ticket_discount: Optional[float] = Field(None, ge=0)
    ticket_discount_type: Optional[Literal["percentage", "fixed"]] = None
    package_discount: Optional[float] = Field(None, ge=0)
    package_discount_type: Optional[Literal["percentage", "fixed"]] = None
    hotel_discounts: Optional[List[HotelDiscountPeriod]] = None
    is_active: Optional[bool] = None

class DiscountResponse(DiscountBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    model_config = {
        "populate_by_name": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }
    }
