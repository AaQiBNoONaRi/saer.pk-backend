from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal

class HotelRoomBase(BaseModel):
    hotel_id: str = Field(..., description="ID of the hotel")
    floor_id: str = Field(..., description="ID of the floor")
    room_number: str = Field(..., description="Room number (e.g. '101')")
    bed_type_id: str = Field(..., description="ID of the bed type configuration")
    status: Literal["VACANT", "BOOKED", "CLEANING"] = Field(default="VACANT")
    x_coordinate: Optional[float] = Field(None, description="X position on floor map")
    y_coordinate: Optional[float] = Field(None, description="Y position on floor map")
    is_active: bool = True

class HotelRoomCreate(HotelRoomBase):
    pass

class HotelRoomUpdate(BaseModel):
    room_number: Optional[str] = None
    bed_type_id: Optional[str] = None
    status: Optional[Literal["VACANT", "BOOKED", "CLEANING"]] = None
    x_coordinate: Optional[float] = None
    y_coordinate: Optional[float] = None
    is_active: Optional[bool] = None

class HotelRoomResponse(HotelRoomBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}
