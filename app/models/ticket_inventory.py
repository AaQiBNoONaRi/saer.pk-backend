"""
Ticket Inventory model and schemas
Comprehensive ticket management including trip type, flight type, stopovers, and pricing
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

class StopoverDetails(BaseModel):
    """Stopover/layover flight details"""
    airline: str
    flight_number: str
    departure_datetime: datetime
    arrival_datetime: datetime
    stopover_city: str
    arrival_city: str
    wait_time: str

class TripDetails(BaseModel):
    """Complete trip details including main flight and optional stopover"""
    # Flight type
    flight_type: Literal["Non-Stop", "1-Stop", "2+ Stops"] = "Non-Stop"
    
    # Main flight details
    airline: str
    flight_number: str
    departure_datetime: datetime
    arrival_datetime: datetime
    departure_city: str
    arrival_city: str
    
    # Stopover details (only if flight has stops)
    stopover: Optional[StopoverDetails] = None

class TicketInventoryBase(BaseModel):
    # Group information
    group_name: str = Field(..., min_length=1, max_length=200)
    group_type: str = Field(..., description="e.g., Umrah, Hajj, Tourism")
    
    # Trip configuration
    trip_type: Literal["One-way", "Round-trip"] = "One-way"
    
    # Departure trip details
    departure_trip: TripDetails
    
    # Return trip details (only for round-trip)
    return_trip: Optional[TripDetails] = None
    
    # Pricing
    buying_price: float = Field(..., ge=0)
    selling_price: float = Field(..., ge=0)
    agent_price: float = Field(..., ge=0)
    
    # Seat allocation
    total_seats: int = Field(..., ge=1)
    available_seats: int = Field(..., ge=0)
    
    # Status
    is_active: bool = True

class TicketInventoryCreate(TicketInventoryBase):
    pass

class TicketInventoryUpdate(BaseModel):
    group_name: Optional[str] = None
    group_type: Optional[str] = None
    trip_type: Optional[Literal["One-way", "Round-trip"]] = None
    departure_trip: Optional[TripDetails] = None
    return_trip: Optional[TripDetails] = None
    buying_price: Optional[float] = Field(None, ge=0)
    selling_price: Optional[float] = Field(None, ge=0)
    agent_price: Optional[float] = Field(None, ge=0)
    total_seats: Optional[int] = Field(None, ge=1)
    available_seats: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None

class TicketInventoryResponse(TicketInventoryBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
