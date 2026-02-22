"""
Employee model and schemas
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal
from datetime import datetime

class EmployeeBase(BaseModel):
    emp_id: str = Field(..., description="Employee ID (ORGEP001, BREMP001, AGCEMP001)")
    entity_type: Literal["organization", "branch", "agency"]
    entity_id: str = Field(..., description="ID of the organization, branch, or agency")
    name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=20)
    role: str = Field(..., description="admin, manager, agent, etc.")
    is_active: bool = True

class EmployeeCreate(EmployeeBase):
    password: str = Field(..., min_length=6)

class EmployeeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=6)

class EmployeeResponse(EmployeeBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class EmployeeLogin(BaseModel):
    emp_id: str
    password: str
