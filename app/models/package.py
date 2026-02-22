"""
Package model and schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class PackageFlightData(BaseModel):
    id: str
    airline: str
    trip_type: str
    departure_city: str
    arrival_city: str
    adult_selling: float
    child_selling: float
    infant_selling: float
    return_flight: Optional[Dict[str, str]] = None

class PackageHotelData(BaseModel):
    id: str
    name: str
    city: str
    check_in: str
    check_out: str
    nights: int
    room_types: List[str]
    hotel_pricing: Dict[str, float] = Field(default={})
    selected_room_types: Dict[str, bool] = Field(default={})

class PackageServiceData(BaseModel):
    id: str
    title: str
    purchasing: float
    selling: float

class PackageTransportData(BaseModel):
    id: str
    title: str
    sector: str
    purchasing: float
    selling: float

class PackageBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    pax_capacity: Optional[str] = None
    description: Optional[str] = None
    flight: Optional[PackageFlightData] = None
    hotels: List[PackageHotelData] = Field(default=[])
    food: Optional[PackageServiceData] = None
    ziyarat: Optional[PackageServiceData] = None
    transport: Optional[PackageTransportData] = None
    visa_pricing: Dict[str, float] = Field(default={})
    package_prices: Optional[Dict[str, Any]] = Field(default={})
    is_active: bool = True

class PackageCreate(PackageBase):
    pass

class PackageUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    pax_capacity: Optional[str] = None
    description: Optional[str] = None
    flight: Optional[PackageFlightData] = None
    hotels: Optional[List[PackageHotelData]] = None
    food: Optional[PackageServiceData] = None
    ziyarat: Optional[PackageServiceData] = None
    transport: Optional[PackageTransportData] = None
    visa_pricing: Optional[Dict[str, float]] = None
    package_prices: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    package_prices: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class PackageResponse(PackageBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
