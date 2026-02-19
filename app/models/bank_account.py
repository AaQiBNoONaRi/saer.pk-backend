"""
Bank Account model and schemas
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId

class BankAccountBase(BaseModel):
    organization_id: str
    agency_id: Optional[str] = None # If None, it belongs to the organization directly or branch
    branch_id: Optional[str] = None # New field
    account_type: str = Field(default="Organization", pattern="^(Organization|Branch|Agency)$") # Default for legacy data
    bank_name: str = Field(..., min_length=1, max_length=100)
    account_title: str = Field(..., min_length=1, max_length=100)
    account_number: str = Field(..., min_length=1, max_length=50)
    iban: Optional[str] = Field(None, min_length=1, max_length=50)
    status: str = Field(default="Active") # Active, Inactive
    is_active: bool = True

class BankAccountCreate(BankAccountBase):
    organization_id: Optional[str] = None # Will be set from token or derived
    account_type: str = Field(..., pattern="^(Organization|Branch|Agency)$")

class BankAccountUpdate(BaseModel):
    bank_name: Optional[str] = Field(None, min_length=1, max_length=100)
    account_title: Optional[str] = Field(None, min_length=1, max_length=100)
    account_number: Optional[str] = Field(None, min_length=1, max_length=50)
    iban: Optional[str] = Field(None, min_length=1, max_length=50)
    status: Optional[str] = None
    is_active: Optional[bool] = None

class BankAccountResponse(BankAccountBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            ObjectId: lambda v: str(v)
        }
