from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class PaymentBase(BaseModel):
    booking_id: str = Field(..., description="ID of the related booking")
    booking_type: str = Field(..., description="Type of booking (ticket, umrah, custom)")
    payment_method: str = Field(..., description="bank, cheque, cash, credit, etc.")
    amount: float = Field(..., ge=0, description="Payment amount")
    payment_date: str = Field(..., description="Date of payment")
    note: Optional[str] = Field(None, description="Optional notes")
    status: str = Field(default="pending", description="Status: pending, approved, rejected")
    
    # Optional fields depending on payment method
    slip_url: Optional[str] = Field(None, description="URL path to the uploaded payment slip")
    beneficiary_account: Optional[str] = Field(None, description="Organization bank account details")
    agent_account: Optional[str] = Field(None, description="Agent's bank account details")
    
    # Cash specific fields
    bank_name: Optional[str] = Field(None, description="Bank name for cash deposit")
    depositor_name: Optional[str] = Field(None, description="Name of cash depositor")
    depositor_cnic: Optional[str] = Field(None, description="CNIC of cash depositor")

class PaymentCreate(PaymentBase):
    pass

class PaymentUpdate(BaseModel):
    status: Optional[str] = None
    note: Optional[str] = None

class PaymentResponse(PaymentBase):
    id: str = Field(alias="_id")
    agency_id: Optional[str] = None
    branch_id: Optional[str] = None
    agent_name: Optional[str] = None
    organization_id: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }
