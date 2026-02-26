from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class DiscountDetails(BaseModel):
    type: Optional[str] = None  # e.g., 'percentage' or 'fixed'
    amount: Optional[float] = None
    description: Optional[str] = None


class DiscountedHotelBase(BaseModel):
    name: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1)
    discount: Optional[DiscountDetails] = None
    is_active: bool = True


class DiscountedHotelCreate(DiscountedHotelBase):
    pass


class DiscountedHotelUpdate(BaseModel):
    name: Optional[str] = None
    city: Optional[str] = None
    discount: Optional[DiscountDetails] = None
    is_active: Optional[bool] = None


class DiscountedHotelResponse(DiscountedHotelBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    created_by_employee_id: Optional[str] = None
    organization_id: Optional[str] = None

    model_config = {
        "populate_by_name": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }
