"""
Service Charge model and schemas for fee management
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime, date

class HotelServiceChargePeriod(BaseModel):
    """Hotel service charge period with room-specific charges"""
    quint_charge: float = Field(default=0, ge=0)
    quad_charge: float = Field(default=0, ge=0)
    triple_charge: float = Field(default=0, ge=0)
    double_charge: float = Field(default=0, ge=0)
    sharing_charge: float = Field(default=0, ge=0)
    other_charge: float = Field(default=0, ge=0)
    hotels: List[str] = Field(default_factory=list)
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None

class ServiceChargeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Service charge group name")
    ticket_charge: float = Field(default=0, ge=0, description="Group ticket service charge amount")
    ticket_charge_type: Literal["percentage", "fixed"] = Field(default="fixed", description="Charge type for tickets")
    package_charge: float = Field(default=0, ge=0, description="Umrah package service charge amount")
    package_charge_type: Literal["percentage", "fixed"] = Field(default="fixed", description="Charge type for packages")
    hotel_charges: List[HotelServiceChargePeriod] = Field(default_factory=list, description="Hotel service charge periods")
    is_active: bool = True
    
    @field_validator('ticket_charge')
    @classmethod
    def validate_ticket_charge(cls, v, info):
        if info.data.get('ticket_charge_type') == 'percentage' and v > 100:
            raise ValueError('Percentage charge cannot exceed 100%')
        return v
    
    @field_validator('package_charge')
    @classmethod
    def validate_package_charge(cls, v, info):
        if info.data.get('package_charge_type') == 'percentage' and v > 100:
            raise ValueError('Percentage charge cannot exceed 100%')
        return v

class ServiceChargeCreate(ServiceChargeBase):
    pass

class ServiceChargeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    ticket_charge: Optional[float] = Field(None, ge=0)
    ticket_charge_type: Optional[Literal["percentage", "fixed"]] = None
    package_charge: Optional[float] = Field(None, ge=0)
    package_charge_type: Optional[Literal["percentage", "fixed"]] = None
    hotel_charges: Optional[List[HotelServiceChargePeriod]] = None
    is_active: Optional[bool] = None

class ServiceChargeResponse(ServiceChargeBase):
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
