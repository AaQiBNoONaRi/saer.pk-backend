from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional, Literal

class HotelRoomBookingBase(BaseModel):
    hotel_id: str = Field(..., description="Hotel ID")
    room_id: str = Field(..., description="Room ID")
    bed_type_id: str = Field(..., description="Bed Type ID (Snapshot for reporting)")
    
    # Guest Info (Simplified for internal blocking, expandable for full PMS)
    client_name: str = Field(..., min_length=1)
    client_reference: Optional[str] = None
    
    # Date Range
    date_from: date
    date_to: date
    
    status: Literal["BOOKED", "CHECKED_IN", "CHECKED_OUT", "CANCELLED"] = "BOOKED"
    notes: Optional[str] = None

class HotelRoomBookingCreate(HotelRoomBookingBase):
    pass

class HotelRoomBookingUpdate(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    status: Optional[Literal["BOOKED", "CHECKED_IN", "CHECKED_OUT", "CANCELLED"]] = None
    client_name: Optional[str] = None
    notes: Optional[str] = None

class HotelRoomBookingResponse(HotelRoomBookingBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat(), date: lambda v: v.isoformat()}
