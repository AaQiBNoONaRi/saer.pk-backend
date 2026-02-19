"""
Booking model and schemas
Handles ticket bookings with passenger details and inventory management
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime

class PassengerDetail(BaseModel):
    """Individual passenger information"""
    type: Literal["Adult", "Child", "Infant"]
    title: str = Field(..., min_length=1)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    passport_number: str = Field(..., min_length=1, max_length=50)
    date_of_birth: str = Field(..., description="Date in YYYY-MM-DD format")
    passport_issue_date: str = Field(..., description="Date in YYYY-MM-DD format")
    passport_expiry_date: str = Field(..., description="Date in YYYY-MM-DD format")
    country: str = Field(..., min_length=1, max_length=100)

class BookingBase(BaseModel):
    # Reference to ticket/flight
    ticket_id: str = Field(..., description="ID of the ticket being booked")
    booking_type: Literal["ticket", "package", "custom"] = "ticket"
    
    # Complete ticket details (full ticket object from API)
    ticket_details: Optional[Dict[str, Any]] = Field(None, description="Complete ticket information")
    
    # Agency/Agent information (from auth)
    agency_id: Optional[str] = None
    branch_id: Optional[str] = None
    agent_name: Optional[str] = None
    
    # Passenger details
    passengers: List[PassengerDetail] = Field(..., min_items=1)
    total_passengers: int = Field(..., ge=1)
    
    # Pricing breakdown
    base_price_per_person: float = Field(..., ge=0)
    tax_per_person: float = Field(..., ge=0)
    service_charge_per_person: float = Field(..., ge=0)
    subtotal: float = Field(..., ge=0)
    total_tax: float = Field(..., ge=0)
    total_service_charge: float = Field(..., ge=0)
    grand_total: float = Field(..., ge=0)
    
    # Payment details (null until payment step is completed)
    payment_method: Optional[Literal["cash", "card", "bank", "cheque", "credit"]] = None
    payment_status: Optional[Literal["pending", "partial", "paid", "refunded"]] = None
    paid_amount: float = Field(default=0, ge=0)
    
    # Booking status
    booking_status: Literal["pending", "underprocess", "confirmed", "cancelled", "completed"] = "pending"
    
    # Additional information
    notes: Optional[str] = None

class BookingCreate(BookingBase):
    pass

class BookingUpdate(BaseModel):
    payment_method: Optional[Literal["cash", "card", "bank", "cheque", "credit"]] = None
    payment_status: Optional[Literal["pending", "partial", "paid", "refunded"]] = None
    paid_amount: Optional[float] = Field(None, ge=0)
    booking_status: Optional[Literal["pending", "underprocess", "confirmed", "cancelled", "completed"]] = None
    notes: Optional[str] = None

class BookingResponse(BookingBase):
    id: str = Field(alias="_id")
    booking_reference: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        arbitrary_types_allowed = True
