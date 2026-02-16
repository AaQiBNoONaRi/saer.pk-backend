"""
Branch model and schemas
"""
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime

class BranchBase(BaseModel):
    organization_id: str
    name: str = Field(..., min_length=1, max_length=200)
    code: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    is_active: bool = True
    portal_access_enabled: bool = True
    username: Optional[str] = None
    password: Optional[str] = None

class BranchCreate(BranchBase):
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        if v is not None and v != '' and len(v) < 10:
            raise ValueError('Phone number must be at least 10 characters')
        return v

class BranchUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    code: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    is_active: Optional[bool] = None
    portal_access_enabled: Optional[bool] = None
    username: Optional[str] = None
    password: Optional[str] = None
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        if v is not None and v != '' and len(v) < 10:
            raise ValueError('Phone number must be at least 10 characters')
        return v

class BranchResponse(BranchBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
