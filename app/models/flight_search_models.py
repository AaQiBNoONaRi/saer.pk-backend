"""
AIQS Flight Search Data Models
Pydantic models matching AIQS API specification
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import date


class PassengerQuantity(BaseModel):
    """Passenger counts with validation"""
    adt: int = Field(..., ge=1, le=9, description="Adult count (1-9)")
    chd: int = Field(..., ge=0, le=8, description="Child count (0-8)")
    inf: int = Field(..., ge=0, le=9, description="Infant count (0-9)")
    
    @validator('*', pre=True)
    def validate_total(cls, v, values):
        """Ensure total passengers <= 9"""
        if 'adt' in values and 'chd' in values:
            total = values['adt'] + values.get('chd', 0) + v
            if total > 9:
                raise ValueError("Total passengers cannot exceed 9")
        return v


class OriginDestinationPair(BaseModel):
    """Origin-destination pair with IATA codes"""
    departureDate: str = Field(..., description="Departure date in DD-MM-YYYY format")
    originLocation: str = Field(..., min_length=3, max_length=3, description="Origin IATA code")
    destinationLocation: str = Field(..., min_length=3, max_length=3, description="Destination IATA code")
    
    @validator('departureDate')
    def validate_date_format(cls, v):
        """Validate DD-MM-YYYY format"""
        try:
            day, month, year = v.split('-')
            date(int(year), int(month), int(day))
            return v
        except:
            raise ValueError("Date must be in DD-MM-YYYY format")


class CommonRequestSearch(BaseModel):
    """Common search parameters"""
    numberOfUnits: int = Field(..., description="Total passenger count")
    typeOfUnit: str = Field(default="PX", description="Unit type (always PX)")
    resultsCount: str = Field(default="50", description="Max results count")


class FlightCriteria(BaseModel):
    """Flight search criteria"""
    criteriaType: str = Field(default="Air", description="Criteria type")
    commonRequestSearch: CommonRequestSearch
    ondPairs: List[OriginDestinationPair] = Field(..., min_items=1, description="Origin-destination pairs")
    preferredAirline: Optional[List[str]] = Field(default=[], description="Preferred airline codes")
    nonStop: Optional[bool] = Field(default=False, description="Non-stop flights only")
    cabin: str = Field(default="Y", description="Cabin class: M/W/Y/C/F")
    maxStopQuantity: str = Field(default="All", description="Max stops: Direct/All")
    tripType: str = Field(..., description="Trip type: O=Oneway, R=Round, M=Multi")
    target: str = Field(default="Test", description="Target environment")
    paxQuantity: PassengerQuantity
    rangeOfDates: Optional[int] = Field(default=None, description="Range of dates for search")
    
    @validator('cabin')
    def validate_cabin(cls, v):
        """Validate cabin class"""
        valid_cabins = ['M', 'W', 'Y', 'C', 'F']
        if v not in valid_cabins:
            raise ValueError(f"Cabin must be one of {valid_cabins}")
        return v
    
    @validator('tripType')
    def validate_trip_type(cls, v):
        """Validate trip type"""
        valid_types = ['O', 'R', 'M']
        if v not in valid_types:
            raise ValueError(f"Trip type must be one of {valid_types}")
        return v


class FlightSearchRequest(BaseModel):
    """Complete flight search request"""
    service: str = Field(default="FlightRQ", description="Service identifier")
    token: Optional[str] = Field(default=None, description="Auth token (auto-filled)")
    content: Dict[str, Any] = Field(..., description="Search content")
    
    class Config:
        schema_extra = {
            "example": {
                "service": "FlightRQ",
                "content": {
                    "command": "FlightSearchRQ",
                    "criteria": {
                        "criteriaType": "Air",
                        "commonRequestSearch": {
                            "numberOfUnits": 1,
                            "typeOfUnit": "PX",
                            "resultsCount": "50"
                        },
                        "ondPairs": [
                            {
                                "departureDate": "07-03-2026",
                                "originLocation": "KHI",
                                "destinationLocation": "DXB"
                            }
                        ],
                        "preferredAirline": [],
                        "nonStop": False,
                        "cabin": "Y",
                        "maxStopQuantity": "All",
                        "tripType": "O",
                        "target": "Test",
                        "paxQuantity": {
                            "adt": 1,
                            "chd": 0,
                            "inf": 0
                        }
                    }
                }
            }
        }


class FlightIndexFare(BaseModel):
    """Fare information"""
    baseFare: str
    tax: str
    total: float
    currency: str


class FlightIndexResponse(BaseModel):
    """Individual flight result"""
    reccount: Optional[Dict[str, str]] = None
    fare: Optional[FlightIndexFare] = None
    fareDetails: Optional[Dict[str, Any]] = None
    ondPairs: Optional[List[Dict[str, Any]]] = None
    brands: Optional[List[Dict[str, Any]]] = None
    combinationMatrix: Optional[Dict[str, Any]] = None
    refundable: Optional[bool] = None
    instantTicketing: Optional[bool] = None
    bookOnHold: Optional[bool] = None
    supplierSpecific: Optional[Dict[str, Any]] = None
    brandedFareSupported: Optional[bool] = None
    brandedFareSeparate: Optional[bool] = None


class SearchResponse(BaseModel):
    """Search response wrapper"""
    flightIndex: List[FlightIndexResponse] = []
    paxQuantity: Optional[PassengerQuantity] = None


class FlightSearchResponse(BaseModel):
    """Complete flight search response"""
    command: str
    totalPages: Optional[str] = None
    currentPage: Optional[str] = None
    searchResponse: Optional[SearchResponse] = None


class SearchStatusResponse(BaseModel):
    """Search status response"""
    search_id: str
    status: str  # INITIALIZING, IN_PROGRESS, COMPLETED, FAILED
    results: List[FlightIndexResponse] = []
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: str


# --- Fare Rules and Validation Models ---

class AIQSRequestNode(BaseModel):
    agencyCode: str = Field(..., description="Agency code")


class AIQSSelectCredential(BaseModel):
    id: int = Field(..., description="Credential ID")
    officeIdList: Optional[List[Dict[str, Any]]] = None


class SegmentInfo(BaseModel):
    """Flight segment information for rules/validation"""
    flifo: Dict[str, Any]
    flightTypeDetails: Optional[Dict[str, Any]] = None


class FareRuleCriteria(BaseModel):
    """Criteria for fetching fare rules"""
    adt: int
    chd: int
    inf: int
    segmentGroup: List[Dict[str, Any]]
    tripType: str
    from_loc: str = Field(..., alias="from")
    to_loc: str = Field(..., alias="to")


class FareRuleRequest(BaseModel):
    """Request for fare rules"""
    supplierCodes: List[int]
    searchKey: str
    selectCredential: AIQSSelectCredential
    criteria: FareRuleCriteria
    supplierSpecific: List[Dict[str, Any]]


class ValidateFareRequest(BaseModel):
    """Request for price validation"""
    supplierCodes: List[int]
    searchKey: str
    selectCredential: AIQSSelectCredential
    criteria: Dict[str, Any]  # Similar to search criteria but refined
    supplierSpecific: List[Dict[str, Any]]
    brandId: Optional[str] = None


class FareRuleResponse(BaseModel):
    """Response wrapper for fare rules"""
    status: str = "success"
    rules: List[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None


class ValidateFareResponse(BaseModel):
    """Response wrapper for price validation"""
    status: str = "success"
    fare: Dict[str, Any]
    sealed: str
    bookOnHold: bool
    instantTicketing: bool
    metadata: Optional[Dict[str, Any]] = None
