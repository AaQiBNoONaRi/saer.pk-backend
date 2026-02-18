from pydantic import BaseModel, Field, validator
from datetime import date, datetime
from typing import List, Optional

class ContactDetails(BaseModel):
    contact_person: str = Field(..., min_length=1)
    contact_number: str = Field(..., min_length=1)

class HotelPrice(BaseModel):
    date_from: date
    date_to: date
    bed_type_id: str = Field(..., description="ID of the Bed Type")
    room_only_price: float = Field(default=0, ge=0)
    selling_price: float = Field(..., ge=0)
    purchase_price: float = Field(default=0, ge=0)
    
    @validator('date_to')
    def validate_dates(cls, v, values):
        if 'date_from' in values and v < values['date_from']:
            raise ValueError('End date must be after or same as start date')
        return v
    
    @validator('selling_price')
    def validate_margin(cls, v, values):
        # Optional warning or strict check: Selling >= Purchase
        # For now, we allow it (e.g. promotions) but good to have hook
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
    
    # Contact (Simplified Source of Truth)
    contact_number: Optional[str] = None
    contact_details: List[ContactDetails] = []
    
    # Availability Range
    available_from: Optional[date] = None
    available_until: Optional[date] = None
    
    # Pricing (Defines Allowed Bed Types)
    prices: List[HotelPrice] = []
    
    # Media
    photos: List[str] = []
    video: Optional[str] = None
    
    # Settings
    allow_reselling: bool = False
    is_active: bool = True
    
    @validator('available_until')
    def validate_availability(cls, v, values):
        if v and 'available_from' in values and values['available_from'] and v < values['available_from']:
            raise ValueError('Available until must be >= available from')
        return v

class HotelCreate(HotelBase):
    @validator('prices')
    def validate_price_overlap(cls, v):
        # Check for overlapping date ranges for same bed_type_id
        # v is a list of HotelPrice objects
        # Group by bed_type_id
        prices_by_type = {}
        for price in v:
            if price.bed_type_id not in prices_by_type:
                prices_by_type[price.bed_type_id] = []
            prices_by_type[price.bed_type_id].append(price)
            
        # Check overlaps
        for bed_type, prices in prices_by_type.items():
            sorted_prices = sorted(prices, key=lambda p: p.date_from)
            for i in range(len(sorted_prices) - 1):
                current = sorted_prices[i]
                next_price = sorted_prices[i+1]
                # If current ends after next starts -> Overlap
                if current.date_to >= next_price.date_from:
                     raise ValueError(f"Overlapping price dates detected for bed type ID {bed_type}")
        return v
    
    @validator('prices')
    def validate_price_in_availability(cls, v, values):
        avail_from = values.get('available_from')
        avail_to = values.get('available_until')
        
        if avail_from and avail_to:
            for price in v:
                if price.date_from < avail_from or price.date_to > avail_to:
                    raise ValueError(f"Price range {price.date_from}-{price.date_to} is outside hotel availability {avail_from}-{avail_to}")
        return v

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
    category_name: Optional[str] = None # Filled in via aggregation/lookup if needed
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat(), date: lambda v: v.isoformat()}
