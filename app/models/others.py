"""
Others Management models - Configuration for rates, sectors, and service pricing
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

# ============================================================================
# 1. RIYAL RATE MODEL
# ============================================================================
class RiyalRateBase(BaseModel):
    """Base model for Riyal exchange rate configuration"""
    rate: float = Field(..., ge=0, description="Exchange rate from SAR to PKR")
    is_visa_pkr: bool = Field(default=False, description="Show visa prices in PKR")
    is_hotel_pkr: bool = Field(default=False, description="Show hotel prices in PKR")
    is_transport_pkr: bool = Field(default=False, description="Show transport prices in PKR")
    is_ziarat_pkr: bool = Field(default=False, description="Show ziarat prices in PKR")
    is_food_pkr: bool = Field(default=False, description="Show food prices in PKR")

class RiyalRateCreate(RiyalRateBase):
    pass

class RiyalRateUpdate(BaseModel):
    rate: Optional[float] = Field(None, ge=0)
    is_visa_pkr: Optional[bool] = None
    is_hotel_pkr: Optional[bool] = None
    is_transport_pkr: Optional[bool] = None
    is_ziarat_pkr: Optional[bool] = None
    is_food_pkr: Optional[bool] = None

class RiyalRateResponse(RiyalRateBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}

# ============================================================================
# 2. SHIRKA (SAUDI COMPANY) MODEL
# ============================================================================
class ShirkaBase(BaseModel):
    """Base model for Saudi company registration"""
    name: str = Field(..., min_length=1, description="Saudi company name")
    is_active: bool = Field(default=True)

class ShirkaCreate(ShirkaBase):
    pass

class ShirkaUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    is_active: Optional[bool] = None

class ShirkaResponse(ShirkaBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}

# ============================================================================
# 3. SMALL SECTORS MODEL
# ============================================================================
class SmallSectorBase(BaseModel):
    """Base model for short-haul transport sectors"""
    departure_city: str = Field(..., description="Departure city")
    arrival_city: str = Field(..., description="Arrival city")
    sector_type: Literal["AIRPORT PICKUP", "AIRPORT DROP", "HOTEL TO HOTEL"] = "AIRPORT PICKUP"
    contact_name: str = Field(..., description="Contact person name")
    contact_number: str = Field(..., description="Contact phone number")
    is_active: bool = Field(default=True)

class SmallSectorCreate(SmallSectorBase):
    pass

class SmallSectorUpdate(BaseModel):
    departure_city: Optional[str] = None
    arrival_city: Optional[str] = None
    sector_type: Optional[Literal["AIRPORT PICKUP", "AIRPORT DROP", "HOTEL TO HOTEL"]] = None
    contact_name: Optional[str] = None
    contact_number: Optional[str] = None
    is_active: Optional[bool] = None

class SmallSectorResponse(SmallSectorBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}

# ============================================================================
# 4. BIG SECTORS MODEL
# ============================================================================
class BigSectorBase(BaseModel):
    """Base model for bundled sector groups"""
    name: str = Field(..., description="Big sector name/title")
    small_sector_ids: list[str] = Field(default=[], description="IDs of small sectors in this bundle")
    is_active: bool = Field(default=True)

class BigSectorCreate(BigSectorBase):
    pass

class BigSectorUpdate(BaseModel):
    name: Optional[str] = None
    small_sector_ids: Optional[list[str]] = None
    is_active: Optional[bool] = None

class BigSectorResponse(BigSectorBase):
    id: str = Field(alias="_id")
    small_sectors_details: Optional[list[SmallSectorResponse]] = Field(default=[], description="Full details of included small sectors")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}

# ============================================================================
# 5. VISA RATES PEX WISE MODEL
# ============================================================================
class VisaRatesPexBase(BaseModel):
    """Base model for group-sized visa pricing"""
    title: str = Field(..., description="Visa package title")
    person_from: int = Field(..., ge=1, description="Minimum group size")
    person_to: int = Field(..., ge=1, description="Maximum group size")
    
    # Pricing for Adult
    adult_selling: float = Field(default=0, ge=0)
    adult_purchasing: float = Field(default=0, ge=0)
    
    # Pricing for Child
    child_selling: float = Field(default=0, ge=0)
    child_purchasing: float = Field(default=0, ge=0)
    
    # Pricing for Infant
    infant_selling: float = Field(default=0, ge=0)
    infant_purchasing: float = Field(default=0, ge=0)
    
    # Associated resources
    vehicle_ids: list[str] = Field(default=[], description="Associated vehicle IDs")
    with_transport: bool = Field(default=False)
    
    is_active: bool = Field(default=True)

class VisaRatesPexCreate(VisaRatesPexBase):
    pass

class VisaRatesPexUpdate(BaseModel):
    title: Optional[str] = None
    person_from: Optional[int] = Field(None, ge=1)
    person_to: Optional[int] = Field(None, ge=1)
    adult_selling: Optional[float] = Field(None, ge=0)
    adult_purchasing: Optional[float] = Field(None, ge=0)
    child_selling: Optional[float] = Field(None, ge=0)
    child_purchasing: Optional[float] = Field(None, ge=0)
    infant_selling: Optional[float] = Field(None, ge=0)
    infant_purchasing: Optional[float] = Field(None, ge=0)
    vehicle_ids: Optional[list[str]] = None
    with_transport: Optional[bool] = None
    is_active: Optional[bool] = None

class VisaRatesPexResponse(VisaRatesPexBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}

# ============================================================================
# 6. ONLY VISA RATES MODEL
# ============================================================================
class OnlyVisaRateBase(BaseModel):
    """Base model for direct visa-only rates"""
    visa_option: Literal["Only", "Long Term"] = "Only"
    status: Literal["Active", "Inactive"] = "Active"
    start_days: int = Field(..., ge=1, description="Validity start in days")
    end_days: int = Field(..., ge=1, description="Validity end in days")
    
    # Pricing
    adult_selling: float = Field(default=0, ge=0)
    adult_purchasing: float = Field(default=0, ge=0)
    child_selling: float = Field(default=0, ge=0)
    child_purchasing: float = Field(default=0, ge=0)
    infant_selling: float = Field(default=0, ge=0)
    infant_purchasing: float = Field(default=0, ge=0)

class OnlyVisaRateCreate(OnlyVisaRateBase):
    pass

class OnlyVisaRateUpdate(BaseModel):
    visa_option: Optional[Literal["Only", "Long Term"]] = None
    status: Optional[Literal["Active", "Inactive"]] = None
    start_days: Optional[int] = Field(None, ge=1)
    end_days: Optional[int] = Field(None, ge=1)
    adult_selling: Optional[float] = Field(None, ge=0)
    adult_purchasing: Optional[float] = Field(None, ge=0)
    child_selling: Optional[float] = Field(None, ge=0)
    child_purchasing: Optional[float] = Field(None, ge=0)
    infant_selling: Optional[float] = Field(None, ge=0)
    infant_purchasing: Optional[float] = Field(None, ge=0)

class OnlyVisaRateResponse(OnlyVisaRateBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}

# ============================================================================
# 7. TRANSPORT PRICES MODEL
# ============================================================================
class TransportPriceBase(BaseModel):
    """Base model for transport/vehicle pricing"""
    vehicle_name: str = Field(..., description="Vehicle name")
    vehicle_type: str = Field(..., description="Bus/Car/Van")
    sector: str = Field(..., description="Sector route")
    sector_id: Optional[str] = Field(None, description="ID of the Small or Big Sector")
    is_big_sector: bool = Field(default=False, description="True if sector_id refers to a Big Sector")
    notes: str = Field(default="", description="Additional notes")
    status: Literal["Active", "Inactive"] = "Active"
    
    # Pricing
    adult_selling: float = Field(default=0, ge=0)
    adult_purchasing: float = Field(default=0, ge=0)
    child_selling: float = Field(default=0, ge=0)
    child_purchasing: float = Field(default=0, ge=0)
    infant_selling: float = Field(default=0, ge=0)
    infant_purchasing: float = Field(default=0, ge=0)

class TransportPriceCreate(TransportPriceBase):
    pass

class TransportPriceUpdate(BaseModel):
    vehicle_name: Optional[str] = None
    vehicle_type: Optional[str] = None
    vehicle_type: Optional[str] = None
    sector: Optional[str] = None
    sector_id: Optional[str] = None
    is_big_sector: Optional[bool] = None
    notes: Optional[str] = None
    status: Optional[Literal["Active", "Inactive"]] = None
    adult_selling: Optional[float] = Field(None, ge=0)
    adult_purchasing: Optional[float] = Field(None, ge=0)
    child_selling: Optional[float] = Field(None, ge=0)
    child_purchasing: Optional[float] = Field(None, ge=0)
    infant_selling: Optional[float] = Field(None, ge=0)
    infant_purchasing: Optional[float] = Field(None, ge=0)

class TransportPriceResponse(TransportPriceBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}

# ============================================================================
# 8. FOOD PRICES MODEL
# ============================================================================
class FoodPriceBase(BaseModel):
    """Base model for food/meal pricing"""
    title: str = Field(..., description="Meal package title")
    city: str = Field(..., description="Makkah or Madinah")
    description: str = Field(default="", description="Package description")
    min_pax: int = Field(default=0, ge=0, description="Minimum passengers")
    per_pax: int = Field(default=0, ge=0, description="Per passenger count")
    
    # Pricing
    adult_selling: float = Field(default=0, ge=0)
    adult_purchasing: float = Field(default=0, ge=0)
    child_selling: float = Field(default=0, ge=0)
    child_purchasing: float = Field(default=0, ge=0)
    infant_selling: float = Field(default=0, ge=0)
    infant_purchasing: float = Field(default=0, ge=0)
    
    is_active: bool = Field(default=True)

class FoodPriceCreate(FoodPriceBase):
    pass

class FoodPriceUpdate(BaseModel):
    title: Optional[str] = None
    city: Optional[str] = None
    description: Optional[str] = None
    min_pax: Optional[int] = Field(None, ge=0)
    per_pax: Optional[int] = Field(None, ge=0)
    adult_selling: Optional[float] = Field(None, ge=0)
    adult_purchasing: Optional[float] = Field(None, ge=0)
    child_selling: Optional[float] = Field(None, ge=0)
    child_purchasing: Optional[float] = Field(None, ge=0)
    infant_selling: Optional[float] = Field(None, ge=0)
    infant_purchasing: Optional[float] = Field(None, ge=0)
    is_active: Optional[bool] = None

class FoodPriceResponse(FoodPriceBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}

# ============================================================================
# 9. ZIARAT PRICES MODEL
# ============================================================================
class ZiaratPriceBase(BaseModel):
    """Base model for ziarat/tour pricing"""
    city: str = Field(..., description="Makkah or Madinah")
    title: str = Field(..., description="Ziarat title")
    contact_person: str = Field(..., description="Contact person")
    contact_number: str = Field(..., description="Contact number")
    min_pax: int = Field(default=1, ge=1, description="Minimum passengers")
    max_pax: int = Field(default=50, ge=1, description="Maximum passengers")
    status: Literal["Active", "Inactive"] = "Active"
    
    # Pricing
    adult_selling: float = Field(default=0, ge=0)
    adult_purchasing: float = Field(default=0, ge=0)
    child_selling: float = Field(default=0, ge=0)
    child_purchasing: float = Field(default=0, ge=0)
    infant_selling: float = Field(default=0, ge=0)
    infant_purchasing: float = Field(default=0, ge=0)

class ZiaratPriceCreate(ZiaratPriceBase):
    pass

class ZiaratPriceUpdate(BaseModel):
    city: Optional[str] = None
    title: Optional[str] = None
    contact_person: Optional[str] = None
    contact_number: Optional[str] = None
    min_pax: Optional[int] = Field(None, ge=1)
    max_pax: Optional[int] = Field(None, ge=1)
    status: Optional[Literal["Active", "Inactive"]] = None
    adult_selling: Optional[float] = Field(None, ge=0)
    adult_purchasing: Optional[float] = Field(None, ge=0)
    child_selling: Optional[float] = Field(None, ge=0)
    child_purchasing: Optional[float] = Field(None, ge=0)
    infant_selling: Optional[float] = Field(None, ge=0)
    infant_purchasing: Optional[float] = Field(None, ge=0)

class ZiaratPriceResponse(ZiaratPriceBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}

# ============================================================================
# 10. FLIGHT IATA MODEL
# ============================================================================
class FlightIATABase(BaseModel):
    """Base model for airline registry"""
    airline_name: str = Field(..., description="Full airline name")
    iata_code: str = Field(..., min_length=2, max_length=3, description="2-3 letter IATA code")
    logo_url: Optional[str] = Field(default=None, description="URL/path to airline logo")
    is_active: bool = Field(default=True)

class FlightIATACreate(FlightIATABase):
    pass

class FlightIATAUpdate(BaseModel):
    airline_name: Optional[str] = None
    iata_code: Optional[str] = Field(None, min_length=2, max_length=3)
    logo_url: Optional[str] = None
    is_active: Optional[bool] = None

class FlightIATAResponse(FlightIATABase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}

# ============================================================================
# 11. CITY IATA MODEL
# ============================================================================
class CityIATABase(BaseModel):
    """Base model for city/airport registry"""
    city_name: str = Field(..., description="City name")
    iata_code: str = Field(..., min_length=3, max_length=3, description="3-letter IATA code")
    is_active: bool = Field(default=True)

class CityIATACreate(CityIATABase):
    pass

class CityIATAUpdate(BaseModel):
    city_name: Optional[str] = None
    iata_code: Optional[str] = Field(None, min_length=3, max_length=3)
    is_active: Optional[bool] = None

class CityIATAResponse(CityIATABase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}

# ============================================================================
# 12. BOOKING EXPIRY SETTINGS MODEL
# ============================================================================
class BookingExpiryBase(BaseModel):
    """Base model for booking expiration timers"""
    group_booking_hours: int = Field(default=24, ge=0, le=24)
    group_booking_minutes: int = Field(default=0, ge=0, le=59)
    
    umrah_booking_hours: int = Field(default=24, ge=0, le=24)
    umrah_booking_minutes: int = Field(default=0, ge=0, le=59)
    
    customer_booking_hours: int = Field(default=24, ge=0, le=24)
    customer_booking_minutes: int = Field(default=0, ge=0, le=59)
    
    custom_umrah_hours: int = Field(default=24, ge=0, le=24)
    custom_umrah_minutes: int = Field(default=0, ge=0, le=59)

class BookingExpiryCreate(BookingExpiryBase):
    pass

class BookingExpiryUpdate(BaseModel):
    group_booking_hours: Optional[int] = Field(None, ge=0, le=24)
    group_booking_minutes: Optional[int] = Field(None, ge=0, le=59)
    umrah_booking_hours: Optional[int] = Field(None, ge=0, le=24)
    umrah_booking_minutes: Optional[int] = Field(None, ge=0, le=59)
    customer_booking_hours: Optional[int] = Field(None, ge=0, le=24)
    customer_booking_minutes: Optional[int] = Field(None, ge=0, le=59)
    custom_umrah_hours: Optional[int] = Field(None, ge=0, le=24)
    custom_umrah_minutes: Optional[int] = Field(None, ge=0, le=59)

class BookingExpiryResponse(BookingExpiryBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}
