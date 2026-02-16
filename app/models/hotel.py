"""
Hotel model and schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class RoomCategory(BaseModel):
    type: str = Field(..., description="Quad, Triple, Double, etc.")
    price: float = Field(..., ge=0)
    total_capacity: int = Field(..., ge=0)
    available_capacity: int = Field(..., ge=0)

class HotelBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    city: str = Field(..., min_length=1, max_length=100)
    star_rating: int = Field(..., ge=1, le=5)
    distance_from_haram: float = Field(..., ge=0, description="Distance in meters")
    floors: List[str] = Field(default=[], description="List of floor numbers/names")
    room_categories: List[RoomCategory] = Field(default=[])
    is_active: bool = True

class HotelCreate(HotelBase):
    pass

class HotelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    city: Optional[str] = None
    star_rating: Optional[int] = Field(None, ge=1, le=5)
    distance_from_haram: Optional[float] = Field(None, ge=0)
    floors: Optional[List[str]] = None
    room_categories: Optional[List[RoomCategory]] = None
    is_active: Optional[bool] = None

class HotelResponse(HotelBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
