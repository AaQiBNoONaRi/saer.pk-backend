"""
Flight/Ticket model and schemas
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
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
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
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    
    # Stopover details (only if flight has stops)
    stopover: Optional[StopoverDetails] = None

class FlightBase(BaseModel):
    # Trip configuration
    organization_id: Optional[str] = None  # Optional — set server-side from JWT token
    trip_type: Literal["One-way", "Round-trip"] = "One-way"
    
    # Departure trip details
    departure_trip: TripDetails
    
    # Return trip details (only for round-trip)
    return_trip: Optional[TripDetails] = None
    
    # Detailed Pricing (Adult, Child, Infant)
    adult_selling: float = Field(default=0, ge=0)
    adult_purchasing: float = Field(default=0, ge=0)
    child_selling: float = Field(default=0, ge=0)
    child_purchasing: float = Field(default=0, ge=0)
    infant_selling: float = Field(default=0, ge=0)
    infant_purchasing: float = Field(default=0, ge=0)
    
    # Seat allocation
    total_seats: int = Field(..., ge=1)
    available_seats: int = Field(..., ge=0)
    
    # Reselling configuration
    allow_reselling: bool = False
    
    # Status
    is_active: bool = True
    
    # PNR Reference
    pnr: Optional[str] = None

class FlightCreate(FlightBase):
    pass  # organization_id inherited as Optional, set server-side

class FlightUpdate(BaseModel):
    trip_type: Optional[Literal["One-way", "Round-trip"]] = None
    departure_trip: Optional[TripDetails] = None
    return_trip: Optional[TripDetails] = None
    adult_selling: Optional[float] = Field(None, ge=0)
    adult_purchasing: Optional[float] = Field(None, ge=0)
    child_selling: Optional[float] = Field(None, ge=0)
    child_purchasing: Optional[float] = Field(None, ge=0)
    infant_selling: Optional[float] = Field(None, ge=0)
    infant_purchasing: Optional[float] = Field(None, ge=0)
    total_seats: Optional[int] = Field(None, ge=1)
    available_seats: Optional[int] = Field(None, ge=0)
    allow_reselling: Optional[bool] = None
    is_active: Optional[bool] = None

class FlightResponse(FlightBase):
    id: str = Field(alias="_id")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_shared: Optional[bool] = False
    shared_from_org_id: Optional[str] = None

    model_config = {
        "populate_by_name": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }

