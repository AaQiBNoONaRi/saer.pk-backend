"""
Hotel model and schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime, date

class ContactDetail(BaseModel):
    """Contact person details"""
    contact_person: Optional[str] = None
    contact_number: Optional[str] = None

class BedPriceDetail(BaseModel):
    """Bed type pricing within a period"""
    bed_type_id: str
    purchase_price: float = Field(default=0, ge=0)
    selling_price: float = Field(ge=0)
    room_only_price: float = Field(default=0, ge=0)

class HotelPrice(BaseModel):
    """Hotel pricing for a specific period and bed type"""
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    bed_type_id: str
    purchase_price: float = Field(default=0, ge=0)
    selling_price: float = Field(ge=0)
    room_only_price: float = Field(default=0, ge=0)

class HotelBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    city: str = Field(..., min_length=1, max_length=100)
    address: Optional[str] = None
    category_id: Optional[str] = None
    distance_meters: float = Field(default=0, ge=0, description="Distance from Haram in meters")
    walking_time_minutes: int = Field(default=0, ge=0, description="Walking time in minutes")
    walking_distance_meters: float = Field(default=0, ge=0, description="Walking distance in meters")
    contact_number: Optional[str] = None
    google_location_link: Optional[str] = None
    available_from: Optional[date] = None
    available_until: Optional[date] = None
    contact_details: List[ContactDetail] = Field(default_factory=list)
    prices: List[HotelPrice] = Field(default_factory=list, description="Flat array of bed type prices per period")
    photos: List[str] = Field(default_factory=list, description="Array of photo URLs")
    video_url: Optional[str] = None
    allow_reselling: bool = Field(default=False)
    is_active: bool = Field(default=True)

class HotelCreate(HotelBase):
    pass

class HotelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    city: Optional[str] = None
    address: Optional[str] = None
    category_id: Optional[str] = None
    distance_meters: Optional[float] = Field(None, ge=0)
    walking_time_minutes: Optional[int] = Field(None, ge=0)
    walking_distance_meters: Optional[float] = Field(None, ge=0)
    contact_number: Optional[str] = None
    google_location_link: Optional[str] = None
    available_from: Optional[date] = None
    available_until: Optional[date] = None
    contact_details: Optional[List[ContactDetail]] = None
    prices: Optional[List[HotelPrice]] = None
    photos: Optional[List[str]] = None
    video_url: Optional[str] = None
    allow_reselling: Optional[bool] = None
    is_active: Optional[bool] = None

class HotelResponse(HotelBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }
