"""
Agency model and schemas
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class AgencyBase(BaseModel):
    organization_id: str
    branch_id: str
    name: str = Field(..., min_length=1, max_length=200)
    code: Optional[str] = None
    agency_type: Optional[str] = None
    contact_person: Optional[str] = None
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=20)
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    username: Optional[str] = None
    credit_limit: float = Field(default=0.0, ge=0)
    credit_used: float = Field(default=0.0, ge=0)
    credit_limit_days: Optional[int] = Field(default=30)
    agreement_status: Optional[str] = Field(default="active")
    commission_group: Optional[str] = Field(default="Standard")
    portal_access_enabled: bool = False
    is_active: bool = True

class AgencyCreate(AgencyBase):
    password: Optional[str] = Field(None, min_length=6)

class AgencyLogin(BaseModel):
    """Agency login credentials"""
    email: EmailStr
    password: str

class AgencyUpdate(BaseModel):
    branch_id: Optional[str] = None
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    code: Optional[str] = None
    agency_type: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6)
    credit_limit: Optional[float] = Field(None, ge=0)
    credit_used: Optional[float] = Field(None, ge=0)
    portal_access_enabled: Optional[bool] = None
    is_active: Optional[bool] = None

class AgencyResponse(AgencyBase):
    id: str = Field(alias="_id")
    available_credit: float
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
