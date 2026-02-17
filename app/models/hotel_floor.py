from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class HotelFloorBase(BaseModel):
    hotel_id: str = Field(..., description="ID of the hotel this floor belongs to")
    floor_number: str = Field(..., description="Floor number or identifier (e.g. '1', 'G', 'B1')")
    name: Optional[str] = Field(None, description="Optional name (e.g. 'Executive Floor')")
    map_image: Optional[str] = Field(None, description="URL/Path to floor map image")
    is_active: bool = True

class HotelFloorCreate(HotelFloorBase):
    pass

class HotelFloorUpdate(BaseModel):
    floor_number: Optional[str] = None
    name: Optional[str] = None
    map_image: Optional[str] = None
    is_active: Optional[bool] = None

class HotelFloorResponse(HotelFloorBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}
