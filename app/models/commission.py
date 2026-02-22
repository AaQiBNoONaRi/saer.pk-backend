"""
Commission model and schemas for partner earnings management
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime, date

class HotelCommissionPeriod(BaseModel):
    """Hotel commission period with room-specific commissions"""
    quint_commission: float = Field(default=0, ge=0)
    quad_commission: float = Field(default=0, ge=0)
    triple_commission: float = Field(default=0, ge=0)
    double_commission: float = Field(default=0, ge=0)
    sharing_commission: float = Field(default=0, ge=0)
    other_commission: float = Field(default=0, ge=0)
    hotels: List[str] = Field(default_factory=list)
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None

class CommissionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Commission group name")
    ticket_commission: float = Field(default=0, ge=0, description="Group ticket commission amount")
    ticket_commission_type: Literal["percentage", "fixed"] = Field(default="fixed", description="Commission type for tickets")
    package_commission: float = Field(default=0, ge=0, description="Umrah package commission amount")
    package_commission_type: Literal["percentage", "fixed"] = Field(default="fixed", description="Commission type for packages")
    hotel_commissions: List[HotelCommissionPeriod] = Field(default_factory=list, description="Hotel commission periods")
    is_active: bool = True
    
    @field_validator('ticket_commission')
    @classmethod
    def validate_ticket_commission(cls, v, info):
        if info.data.get('ticket_commission_type') == 'percentage' and v > 100:
            raise ValueError('Percentage commission cannot exceed 100%')
        return v
    
    @field_validator('package_commission')
    @classmethod
    def validate_package_commission(cls, v, info):
        if info.data.get('package_commission_type') == 'percentage' and v > 100:
            raise ValueError('Percentage commission cannot exceed 100%')
        return v

class CommissionCreate(CommissionBase):
    pass

class CommissionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    ticket_commission: Optional[float] = Field(None, ge=0)
    ticket_commission_type: Optional[Literal["percentage", "fixed"]] = None
    package_commission: Optional[float] = Field(None, ge=0)
    package_commission_type: Optional[Literal["percentage", "fixed"]] = None
    hotel_commissions: Optional[List[HotelCommissionPeriod]] = None
    is_active: Optional[bool] = None

class CommissionResponse(CommissionBase):
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
