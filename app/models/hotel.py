"""
Hotel model and schemas
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any, Dict, Union
from datetime import datetime, date

class ContactDetail(BaseModel):
    """Contact person details"""
    contact_person: Optional[str] = None
    contact_number: Optional[str] = None

    @field_validator('contact_number', mode='before')
    @classmethod
    def coerce_contact_number(cls, v):
        if v is not None:
            return str(v)
        return v

class BedPriceDetail(BaseModel):
    """Bed type pricing within a period"""
    bed_type_id: str
    purchase_price: float = Field(default=0, ge=0)
    selling_price: float = Field(ge=0)
    room_only_price: float = Field(default=0, ge=0)

def _coerce_to_date(v):
    """Convert datetime / ISO string with timezone to a plain date."""
    if v is None:
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        # strip timezone, parse just the date part
        try:
            return datetime.fromisoformat(v.replace('Z', '+00:00')).date()
        except Exception:
            pass
        try:
            return date.fromisoformat(v[:10])
        except Exception:
            pass
    return v


class HotelPrice(BaseModel):
    """Hotel pricing for a specific period and bed type"""
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    bed_type_id: str
    purchase_price: float = Field(default=0, ge=0)
    selling_price: float = Field(ge=0)
    room_only_price: float = Field(default=0, ge=0)

    @field_validator('date_from', 'date_to', mode='before')
    @classmethod
    def coerce_price_dates(cls, v):
        return _coerce_to_date(v)

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

    @field_validator('contact_number', mode='before')
    @classmethod
    def coerce_contact_number(cls, v):
        if v is not None:
            return str(v)
        return v

    @field_validator('available_from', 'available_until', mode='before')
    @classmethod
    def coerce_availability_dates(cls, v):
        return _coerce_to_date(v)

    @field_validator('available_until', mode='after')
    @classmethod
    def validate_availability(cls, v, info):
        available_from = info.data.get('available_from')
        if v and available_from and v < available_from:
            raise ValueError('Available until must be >= available from')
        return v

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
    
    organization_id: Optional[str] = None
    category_name: Optional[str] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }
    }
