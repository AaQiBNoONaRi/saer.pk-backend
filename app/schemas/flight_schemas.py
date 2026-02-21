"""
Pydantic schemas for the Flight Search module.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Union, Any


# ─── Requests ───────────────────────────────────────────────────────────

class MultiCitySegment(BaseModel):
    origin: str
    destination: str
    departureDate: str  # DD-MM-YYYY


class FlightSearchRequest(BaseModel):
    tripType: str = Field("oneway", description="oneway | roundtrip | multicity")
    # For oneway / roundtrip — optional for multicity (uses multiCitySegments instead)
    origin: Optional[str] = Field(None, min_length=3, max_length=3)
    destination: Optional[str] = Field(None, min_length=3, max_length=3)
    departureDate: Optional[str] = Field(None, description="DD-MM-YYYY")
    returnDate: Optional[str] = None
    adults: int = Field(1, ge=1, le=9)
    children: int = Field(0, ge=0, le=8)
    infants: int = Field(0, ge=0, le=4)
    cabinClass: str = Field("Y", description="Y=Economy, W=PremEco, C=Business, F=First")
    nonStop: bool = False
    preferredAirlines: List[str] = []
    maxResults: int = Field(50, ge=1, le=200)
    multiCitySegments: List[MultiCitySegment] = []


class FlightValidateRequest(BaseModel):
    """Revalidate pricing for a selected flight."""
    supplierCode: Optional[Union[int, str]] = None
    supplierSpecific: Optional[Any] = None
    rawData: dict = Field(..., description="Full raw flight data from search result")
    # Passenger counts — pass from search params since rawData may not contain them
    adt: int = Field(1, description="Adult count")
    chd: int = Field(0, description="Child count")
    inf: int = Field(0, description="Infant count")
    tripType: str = Field("O", description="O=OneWay, R=Return, M=MultiCity")
    searchKey: Optional[str] = Field(None, description="searchKey from search response")



class FareRulesRequest(BaseModel):
    """Request fare rules for a segment."""
    supplierCode: Optional[Union[int, str]] = None
    supplierSpecific: Optional[Any] = None
    segIDs: List[str] = Field(default_factory=list)
    rawData: Optional[dict] = None


class AncillaryRequest(BaseModel):
    """Request for ancillary services (meals, baggage, branded fares). Requires rawData from search result."""
    supplierCode: Optional[Union[int, str]] = None
    supplierSpecific: Optional[Any] = None
    rawData: Optional[dict] = None


class FlightBookRequest(BaseModel):
    """Create a PNR booking via AIQS FlightBookRQ."""
    rawData: dict = Field(..., description="Full raw flight data (ondPairs, fare, etc.)")
    supplierCode: Optional[Union[int, str]] = None
    supplierSpecific: Optional[Any] = None
    validatedSupplierSpecific: Optional[Any] = None
    sealed: Optional[str] = Field(None, description="Sealed token returned from /validate")
    passengers: List[dict] = Field(..., description="List of passenger objects")
    adt: int = Field(1)
    chd: int = Field(0)
    inf: int = Field(0)
    tripType: str = Field("O")
    searchKey: Optional[str] = None




# ─── Responses ──────────────────────────────────────────────────────────

class AuthTokenResponse(BaseModel):
    access_token: str
    id_token: str
    expires_in: int


class FareInfo(BaseModel):
    baseFare: float = 0
    tax: float = 0
    total: float = 0
    currency: str = "PKR"


class FlightLeg(BaseModel):
    departureDate: Optional[str] = None
    departureTime: Optional[str] = None
    arrivalDate: Optional[str] = None
    arrivalTime: Optional[str] = None
    departureLocation: Optional[str] = None
    departureTerminal: Optional[str] = None
    arrivalLocation: Optional[str] = None
    arrivalTerminal: Optional[str] = None
    airlineCode: Optional[str] = None
    operatingAirline: Optional[str] = None
    flightNo: Optional[str] = None
    equipmentType: Optional[str] = None
    duration: Optional[str] = None
    cabin: Optional[str] = None
    stops: int = 0
    seatsAvailable: Optional[Union[int, str]] = None
    baggage: list = []
    segID: Optional[Union[int, str]] = None


class OndInfo(BaseModel):
    duration: Optional[str] = None
    issuingAirline: Optional[str] = None
    ondID: Optional[Union[int, str]] = None


class FlightSegment(BaseModel):
    ond: OndInfo = OndInfo()
    flights: List[FlightLeg] = []


class BrandOption(BaseModel):
    brandId: Optional[Union[int, str]] = None
    brandName: Optional[str] = None
    ondID: Optional[Union[int, str]] = None
    baseFare: float = 0
    tax: float = 0
    total: float = 0
    currency: str = "PKR"
    fareBreakup: list = []
    inclusions: dict = {}
    supplierSpecific: dict = {}


class ParsedFlight(BaseModel):
    id: Optional[Union[int, str]] = None
    refundable: bool = False
    instantTicketing: bool = False
    bookOnHold: bool = False
    brandedFareSupported: bool = False
    fareRuleOffered: bool = False
    fare: FareInfo = FareInfo()
    fareDetails: dict = {}
    segments: List[FlightSegment] = []
    supplierCode: Optional[Union[int, str]] = None
    supplierSpecific: Optional[Any] = None
    brands: List[BrandOption] = []
    rawData: Optional[dict] = None


class FlightSearchResponse(BaseModel):
    flights: List[ParsedFlight] = []
    total_count: int = 0
    request_count: int = 0
