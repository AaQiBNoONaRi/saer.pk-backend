from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional
from datetime import datetime
from bson import ObjectId

class AdminBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)
    organization_id: str
    role: str = Field(default="admin")  # "super_admin" or "admin"
    is_active: bool = Field(default=True)

    @validator('role')
    def validate_role(cls, v):
        if v not in ['admin', 'super_admin']:
            raise ValueError('Role must be either "admin" or "super_admin"')
        return v

class AdminCreate(AdminBase):
    password: str = Field(..., min_length=6)

class AdminUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

class AdminInDB(AdminBase):
    id: str = Field(alias="_id")
    password: str
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}

class AdminResponse(BaseModel):
    id: str = Field(alias="_id")
    username: str
    email: str
    full_name: str
    organization_id: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}

class AdminLogin(BaseModel):
    username: str
    password: str

class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: AdminResponse
