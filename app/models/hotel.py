from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import date, datetime
from typing import List, Optional

class ContactDetails(BaseModel):
    contact_person: str = Field(..., min_length=1)
    contact_number: str = Field(..., min_length=1)

class HotelPrice(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    bed_type_id: str = Field(..., description="ID of the Bed Type")
    room_only_price: float = Field(default=0, ge=0)
    selling_price: float = Field(..., ge=0)
    purchase_price: float = Field(default=0, ge=0)

    @field_validator('date_to', mode='after')
    @classmethod
    def validate_dates(cls, v, info):
        date_from = info.data.get('date_from')
        if v and date_from and v < date_from:
            raise ValueError('End date must be after or same as start date')
        return v

class HotelBase(BaseModel):
    # Basic Info
    city: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    address: Optional[str] = Field(default=None)
    category_id: Optional[str] = None
    bed_type_id: Optional[str] = None

    # Distance & Location
    distance_meters: Optional[float] = Field(None, ge=0)
    walking_time_minutes: Optional[int] = Field(None, ge=0)
    walking_distance_meters: Optional[float] = Field(None, ge=0)
    google_location_link: Optional[str] = None

    # Contact
    contact_number: Optional[str] = None
    contact_details: List[ContactDetails] = []

    # Availability Range
    available_from: Optional[date] = None
    available_until: Optional[date] = None

    # Pricing
    prices: List[HotelPrice] = []

    # Media
    photos: List[str] = []
    video: Optional[str] = None

    # Settings
    allow_reselling: bool = False
    is_active: bool = True

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
    city: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    category_id: Optional[str] = None
    distance_meters: Optional[float] = None
    walking_time_minutes: Optional[int] = None
    walking_distance_meters: Optional[float] = None
    google_location_link: Optional[str] = None
    contact_number: Optional[str] = None
    contact_details: Optional[List[ContactDetails]] = None
    available_from: Optional[date] = None
    available_until: Optional[date] = None
    prices: Optional[List[HotelPrice]] = None
    photos: Optional[List[str]] = None
    video: Optional[str] = None
    allow_reselling: Optional[bool] = None
    is_active: Optional[bool] = None

class HotelResponse(HotelBase):
    id: str = Field(alias="_id")
    category_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }
