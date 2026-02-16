"""
Others Management Routes - Comprehensive API endpoints for all configuration sections
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from datetime import datetime
from app.models.others import (
    # Riyal Rates
    RiyalRateCreate, RiyalRateUpdate, RiyalRateResponse,
    # Shirka
    ShirkaCreate, ShirkaUpdate, ShirkaResponse,
    # Small Sectors
    SmallSectorCreate, SmallSectorUpdate, SmallSectorResponse,
    # Big Sectors
    BigSectorCreate, BigSectorUpdate, BigSectorResponse,
    # Visa Rates Pex
    VisaRatesPexCreate, VisaRatesPexUpdate, VisaRatesPexResponse,
    # Only Visa Rates
    OnlyVisaRateCreate, OnlyVisaRateUpdate, OnlyVisaRateResponse,
    # Transport Prices
    TransportPriceCreate, TransportPriceUpdate, TransportPriceResponse,
    # Food Prices
    FoodPriceCreate, FoodPriceUpdate, FoodPriceResponse,
    # Ziarat Prices
    ZiaratPriceCreate, ZiaratPriceUpdate, ZiaratPriceResponse,
    # Flight IATA
    FlightIATACreate, FlightIATAUpdate, FlightIATAResponse,
    # City IATA
    CityIATACreate, CityIATAUpdate, CityIATAResponse,
    # Booking Expiry
    BookingExpiryCreate, BookingExpiryUpdate, BookingExpiryResponse
)
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user

router = APIRouter(prefix="/others", tags=["Others Management"])

# ============================================================================
# 1. RIYAL RATE ENDPOINTS
# ============================================================================

@router.post("/riyal-rate", response_model=RiyalRateResponse, status_code=status.HTTP_201_CREATED)
async def create_riyal_rate(
    rate: RiyalRateCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create riyal exchange rate configuration"""
    rate_dict = rate.model_dump()
    created = await db_ops.create(Collections.RIYAL_RATES, rate_dict)
    return serialize_doc(created)

@router.get("/riyal-rate", response_model=List[RiyalRateResponse])
async def get_riyal_rates(current_user: dict = Depends(get_current_user)):
    """Get all riyal rate configurations"""
    rates = await db_ops.get_all(Collections.RIYAL_RATES, {})
    return serialize_docs(rates)

@router.get("/riyal-rate/active", response_model=RiyalRateResponse)
async def get_active_riyal_rate(current_user: dict = Depends(get_current_user)):
    """Get the most recent (active) riyal rate"""
    rates = await db_ops.get_all(Collections.RIYAL_RATES, {}, limit=100)
    if not rates:
        raise HTTPException(status_code=404, detail="No riyal rate found")
    # Sort by created_at in Python (most recent first)
    rates_sorted = sorted(rates, key=lambda x: x.get('created_at', datetime.min), reverse=True)
    return serialize_doc(rates_sorted[0])

@router.put("/riyal-rate/{rate_id}", response_model=RiyalRateResponse)
async def update_riyal_rate(
    rate_id: str,
    rate_update: RiyalRateUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update riyal rate configuration"""
    update_data = rate_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await db_ops.update(Collections.RIYAL_RATES, rate_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Riyal rate not found")
    return serialize_doc(updated)

@router.delete("/riyal-rate/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_riyal_rate(
    rate_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete riyal rate configuration"""
    deleted = await db_ops.delete(Collections.RIYAL_RATES, rate_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Riyal rate not found")

# ============================================================================
# 2. SHIRKA ENDPOINTS
# ============================================================================

@router.post("/shirka", response_model=ShirkaResponse, status_code=status.HTTP_201_CREATED)
async def create_shirka(
    shirka: ShirkaCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new shirka (Saudi company)"""
    shirka_dict = shirka.model_dump()
    created = await db_ops.create(Collections.SHIRKAS, shirka_dict)
    return serialize_doc(created)

@router.get("/shirka", response_model=List[ShirkaResponse])
async def get_shirkas(
    is_active: bool = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all shirkas"""
    filter_query = {}
    if is_active is not None:
        filter_query["is_active"] = is_active
    shirkas = await db_ops.get_all(Collections.SHIRKAS, filter_query)
    return serialize_docs(shirkas)

@router.get("/shirka/{shirka_id}", response_model=ShirkaResponse)
async def get_shirka(
    shirka_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get shirka by ID"""
    shirka = await db_ops.get_by_id(Collections.SHIRKAS, shirka_id)
    if not shirka:
        raise HTTPException(status_code=404, detail="Shirka not found")
    return serialize_doc(shirka)

@router.put("/shirka/{shirka_id}", response_model=ShirkaResponse)
async def update_shirka(
    shirka_id: str,
    shirka_update: ShirkaUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update shirka"""
    update_data = shirka_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await db_ops.update(Collections.SHIRKAS, shirka_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Shirka not found")
    return serialize_doc(updated)

@router.delete("/shirka/{shirka_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shirka(
    shirka_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete shirka"""
    deleted = await db_ops.delete(Collections.SHIRKAS, shirka_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Shirka not found")

# ============================================================================
# 3. SMALL SECTORS ENDPOINTS
# ============================================================================

@router.post("/small-sectors", response_model=SmallSectorResponse, status_code=status.HTTP_201_CREATED)
async def create_small_sector(
    sector: SmallSectorCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new small sector"""
    sector_dict = sector.model_dump()
    created = await db_ops.create(Collections.SMALL_SECTORS, sector_dict)
    return serialize_doc(created)

@router.get("/small-sectors", response_model=List[SmallSectorResponse])
async def get_small_sectors(
    is_active: bool = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all small sectors"""
    filter_query = {}
    if is_active is not None:
        filter_query["is_active"] = is_active
    sectors = await db_ops.get_all(Collections.SMALL_SECTORS, filter_query)
    return serialize_docs(sectors)

@router.get("/small-sectors/{sector_id}", response_model=SmallSectorResponse)
async def get_small_sector(
    sector_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get small sector by ID"""
    sector = await db_ops.get_by_id(Collections.SMALL_SECTORS, sector_id)
    if not sector:
        raise HTTPException(status_code=404, detail="Small sector not found")
    return serialize_doc(sector)

@router.put("/small-sectors/{sector_id}", response_model=SmallSectorResponse)
async def update_small_sector(
    sector_id: str,
    sector_update: SmallSectorUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update small sector"""
    update_data = sector_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await db_ops.update(Collections.SMALL_SECTORS, sector_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Small sector not found")
    return serialize_doc(updated)

@router.delete("/small-sectors/{sector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_small_sector(
    sector_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete small sector"""
    deleted = await db_ops.delete(Collections.SMALL_SECTORS, sector_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Small sector not found")

# ============================================================================
# 4. BIG SECTORS ENDPOINTS
# ============================================================================

@router.post("/big-sectors", response_model=BigSectorResponse, status_code=status.HTTP_201_CREATED)
async def create_big_sector(
    sector: BigSectorCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new big sector bundle"""
    sector_dict = sector.model_dump()
    created = await db_ops.create(Collections.BIG_SECTORS, sector_dict)
    return serialize_doc(created)

@router.get("/big-sectors", response_model=List[BigSectorResponse])
async def get_big_sectors(
    is_active: bool = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all big sectors with populated small sector details"""
    filter_query = {}
    if is_active is not None:
        filter_query["is_active"] = is_active
    
    # 1. Get all Big Sectors
    big_sectors = await db_ops.get_all(Collections.BIG_SECTORS, filter_query)
    
    # 2. Extract all unique Small Sector IDs
    all_small_ids = set()
    for bs in big_sectors:
        if "small_sector_ids" in bs and bs["small_sector_ids"]:
            all_small_ids.update(bs["small_sector_ids"])
            
    # 3. Fetch all referenced Small Sectors in one go
    small_sectors_map = {}
    if all_small_ids:
        # We need to implement a bulk fetch or just fetch all active check
        # For simplicity/speed in this context, fetching all small sectors is okay if not huge dataset
        # Better approach: filter by IDs. db_ops might not have 'in' query exposed easily, 
        # so let's fetch all (or use raw query if possible). 
        # Assuming db_ops.get_all works.
        all_small = await db_ops.get_all(Collections.SMALL_SECTORS)
        small_sectors_map = {str(s["_id"]): s for s in all_small}

    # 4. Populate details
    results = []
    for bs in big_sectors:
        details = []
        if "small_sector_ids" in bs:
            for sid in bs["small_sector_ids"]:
                if sid in small_sectors_map:
                    details.append(serialize_doc(small_sectors_map[sid]))
        bs["small_sectors_details"] = details
        results.append(bs)
        
    return serialize_docs(results)

@router.get("/big-sectors/{sector_id}", response_model=BigSectorResponse)
async def get_big_sector(
    sector_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get big sector by ID with details"""
    sector = await db_ops.get_by_id(Collections.BIG_SECTORS, sector_id)
    if not sector:
        raise HTTPException(status_code=404, detail="Big sector not found")
        
    # Populate details
    details = []
    if "small_sector_ids" in sector:
        # Fetch specifics
        for sid in sector["small_sector_ids"]:
             s = await db_ops.get_by_id(Collections.SMALL_SECTORS, sid)
             if s:
                 details.append(serialize_doc(s))
    
    sector["small_sectors_details"] = details
    return serialize_doc(sector)

@router.put("/big-sectors/{sector_id}", response_model=BigSectorResponse)
async def update_big_sector(
    sector_id: str,
    sector_update: BigSectorUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update big sector"""
    update_data = sector_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await db_ops.update(Collections.BIG_SECTORS, sector_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Big sector not found")
    return serialize_doc(updated)

@router.delete("/big-sectors/{sector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_big_sector(
    sector_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete big sector"""
    deleted = await db_ops.delete(Collections.BIG_SECTORS, sector_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Big sector not found")

# ============================================================================
# 5. VISA RATES PEX WISE ENDPOINTS
# ============================================================================

@router.post("/visa-rates-pex", response_model=VisaRatesPexResponse, status_code=status.HTTP_201_CREATED)
async def create_visa_rate_pex(
    rate: VisaRatesPexCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new visa rate (pax-wise)"""
    rate_dict = rate.model_dump()
    created = await db_ops.create(Collections.VISA_RATES_PEX, rate_dict)
    return serialize_doc(created)

@router.get("/visa-rates-pex", response_model=List[VisaRatesPexResponse])
async def get_visa_rates_pex(
    is_active: bool = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all visa rates (pax-wise)"""
    filter_query = {}
    if is_active is not None:
        filter_query["is_active"] = is_active
    rates = await db_ops.get_all(Collections.VISA_RATES_PEX, filter_query)
    return serialize_docs(rates)

@router.get("/visa-rates-pex/{rate_id}", response_model=VisaRatesPexResponse)
async def get_visa_rate_pex(
    rate_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get visa rate (pax-wise) by ID"""
    rate = await db_ops.get_by_id(Collections.VISA_RATES_PEX, rate_id)
    if not rate:
        raise HTTPException(status_code=404, detail="Visa rate not found")
    return serialize_doc(rate)

@router.put("/visa-rates-pex/{rate_id}", response_model=VisaRatesPexResponse)
async def update_visa_rate_pex(
    rate_id: str,
    rate_update: VisaRatesPexUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update visa rate (pax-wise)"""
    update_data = rate_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await db_ops.update(Collections.VISA_RATES_PEX, rate_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Visa rate not found")
    return serialize_doc(updated)

@router.delete("/visa-rates-pex/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_visa_rate_pex(
    rate_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete visa rate (pax-wise)"""
    deleted = await db_ops.delete(Collections.VISA_RATES_PEX, rate_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Visa rate not found")

# ============================================================================
# 6. ONLY VISA RATES ENDPOINTS
# ============================================================================

@router.post("/only-visa-rates", response_model=OnlyVisaRateResponse, status_code=status.HTTP_201_CREATED)
async def create_only_visa_rate(
    rate: OnlyVisaRateCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new only-visa rate"""
    rate_dict = rate.model_dump()
    created = await db_ops.create(Collections.ONLY_VISA_RATES, rate_dict)
    return serialize_doc(created)

@router.get("/only-visa-rates", response_model=List[OnlyVisaRateResponse])
async def get_only_visa_rates(
    status_filter: str = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all only-visa rates"""
    filter_query = {}
    if status_filter:
        filter_query["status"] = status_filter
    rates = await db_ops.get_all(Collections.ONLY_VISA_RATES, filter_query)
    return serialize_docs(rates)

@router.get("/only-visa-rates/{rate_id}", response_model=OnlyVisaRateResponse)
async def get_only_visa_rate(
    rate_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get only-visa rate by ID"""
    rate = await db_ops.get_by_id(Collections.ONLY_VISA_RATES, rate_id)
    if not rate:
        raise HTTPException(status_code=404, detail="Only-visa rate not found")
    return serialize_doc(rate)

@router.put("/only-visa-rates/{rate_id}", response_model=OnlyVisaRateResponse)
async def update_only_visa_rate(
    rate_id: str,
    rate_update: OnlyVisaRateUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update only-visa rate"""
    update_data = rate_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await db_ops.update(Collections.ONLY_VISA_RATES, rate_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Only-visa rate not found")
    return serialize_doc(updated)

@router.delete("/only-visa-rates/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_only_visa_rate(
    rate_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete only-visa rate"""
    deleted = await db_ops.delete(Collections.ONLY_VISA_RATES, rate_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Only-visa rate not found")

# ============================================================================
# 7. TRANSPORT PRICES ENDPOINTS
# ============================================================================

@router.post("/transport-prices", response_model=TransportPriceResponse, status_code=status.HTTP_201_CREATED)
async def create_transport_price(
    price: TransportPriceCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new transport price"""
    price_dict = price.model_dump()
    created = await db_ops.create(Collections.TRANSPORT_PRICES, price_dict)
    return serialize_doc(created)

@router.get("/transport-prices", response_model=List[TransportPriceResponse])
async def get_transport_prices(
    status_filter: str = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all transport prices"""
    filter_query = {}
    if status_filter:
        filter_query["status"] = status_filter
    prices = await db_ops.get_all(Collections.TRANSPORT_PRICES, filter_query)
    return serialize_docs(prices)

@router.get("/transport-prices/{price_id}", response_model=TransportPriceResponse)
async def get_transport_price(
    price_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get transport price by ID"""
    price = await db_ops.get_by_id(Collections.TRANSPORT_PRICES, price_id)
    if not price:
        raise HTTPException(status_code=404, detail="Transport price not found")
    return serialize_doc(price)

@router.put("/transport-prices/{price_id}", response_model=TransportPriceResponse)
async def update_transport_price(
    price_id: str,
    price_update: TransportPriceUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update transport price"""
    update_data = price_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await db_ops.update(Collections.TRANSPORT_PRICES, price_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Transport price not found")
    return serialize_doc(updated)

@router.delete("/transport-prices/{price_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transport_price(
    price_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete transport price"""
    deleted = await db_ops.delete(Collections.TRANSPORT_PRICES, price_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Transport price not found")

# ============================================================================
# 8. FOOD PRICES ENDPOINTS
# ============================================================================

@router.post("/food-prices", response_model=FoodPriceResponse, status_code=status.HTTP_201_CREATED)
async def create_food_price(
    price: FoodPriceCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new food price"""
    price_dict = price.model_dump()
    created = await db_ops.create(Collections.FOOD_PRICES, price_dict)
    return serialize_doc(created)

@router.get("/food-prices", response_model=List[FoodPriceResponse])
async def get_food_prices(
    is_active: bool = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all food prices"""
    filter_query = {}
    if is_active is not None:
        filter_query["is_active"] = is_active
    prices = await db_ops.get_all(Collections.FOOD_PRICES, filter_query)
    return serialize_docs(prices)

@router.get("/food-prices/{price_id}", response_model=FoodPriceResponse)
async def get_food_price(
    price_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get food price by ID"""
    price = await db_ops.get_by_id(Collections.FOOD_PRICES, price_id)
    if not price:
        raise HTTPException(status_code=404, detail="Food price not found")
    return serialize_doc(price)

@router.put("/food-prices/{price_id}", response_model=FoodPriceResponse)
async def update_food_price(
    price_id: str,
    price_update: FoodPriceUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update food price"""
    update_data = price_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await db_ops.update(Collections.FOOD_PRICES, price_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Food price not found")
    return serialize_doc(updated)

@router.delete("/food-prices/{price_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_food_price(
    price_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete food price"""
    deleted = await db_ops.delete(Collections.FOOD_PRICES, price_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Food price not found")

# ============================================================================
# 9. ZIARAT PRICES ENDPOINTS
# ============================================================================

@router.post("/ziarat-prices", response_model=ZiaratPriceResponse, status_code=status.HTTP_201_CREATED)
async def create_ziarat_price(
    price: ZiaratPriceCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new ziarat price"""
    price_dict = price.model_dump()
    created = await db_ops.create(Collections.ZIARAT_PRICES, price_dict)
    return serialize_doc(created)

@router.get("/ziarat-prices", response_model=List[ZiaratPriceResponse])
async def get_ziarat_prices(
    status_filter: str = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all ziarat prices"""
    filter_query = {}
    if status_filter:
        filter_query["status"] = status_filter
    prices = await db_ops.get_all(Collections.ZIARAT_PRICES, filter_query)
    return serialize_docs(prices)

@router.get("/ziarat-prices/{price_id}", response_model=ZiaratPriceResponse)
async def get_ziarat_price(
    price_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get ziarat price by ID"""
    price = await db_ops.get_by_id(Collections.ZIARAT_PRICES, price_id)
    if not price:
        raise HTTPException(status_code=404, detail="Ziarat price not found")
    return serialize_doc(price)

@router.put("/ziarat-prices/{price_id}", response_model=ZiaratPriceResponse)
async def update_ziarat_price(
    price_id: str,
    price_update: ZiaratPriceUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update ziarat price"""
    update_data = price_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await db_ops.update(Collections.ZIARAT_PRICES, price_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Ziarat price not found")
    return serialize_doc(updated)

@router.delete("/ziarat-prices/{price_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ziarat_price(
    price_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete ziarat price"""
    deleted = await db_ops.delete(Collections.ZIARAT_PRICES, price_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Ziarat price not found")

# ============================================================================
# 10. FLIGHT IATA ENDPOINTS
# ============================================================================

@router.post("/flight-iata", response_model=FlightIATAResponse, status_code=status.HTTP_201_CREATED)
async def create_flight_iata(
    flight: FlightIATACreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new airline registry"""
    flight_dict = flight.model_dump()
    created = await db_ops.create(Collections.FLIGHT_IATA, flight_dict)
    return serialize_doc(created)

@router.get("/flight-iata", response_model=List[FlightIATAResponse])
async def get_flight_iatas(
    is_active: bool = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all airline registries"""
    filter_query = {}
    if is_active is not None:
        filter_query["is_active"] = is_active
    flights = await db_ops.get_all(Collections.FLIGHT_IATA, filter_query)
    return serialize_docs(flights)

@router.get("/flight-iata/{flight_id}", response_model=FlightIATAResponse)
async def get_flight_iata(
    flight_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get airline registry by ID"""
    flight = await db_ops.get_by_id(Collections.FLIGHT_IATA, flight_id)
    if not flight:
        raise HTTPException(status_code=404, detail="Flight IATA not found")
    return serialize_doc(flight)

@router.put("/flight-iata/{flight_id}", response_model=FlightIATAResponse)
async def update_flight_iata(
    flight_id: str,
    flight_update: FlightIATAUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update airline registry"""
    update_data = flight_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await db_ops.update(Collections.FLIGHT_IATA, flight_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Flight IATA not found")
    return serialize_doc(updated)

@router.delete("/flight-iata/{flight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flight_iata(
    flight_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete airline registry"""
    deleted = await db_ops.delete(Collections.FLIGHT_IATA, flight_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Flight IATA not found")

# ============================================================================
# 11. CITY IATA ENDPOINTS
# ============================================================================

@router.post("/city-iata", response_model=CityIATAResponse, status_code=status.HTTP_201_CREATED)
async def create_city_iata(
    city: CityIATACreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new city registry"""
    city_dict = city.model_dump()
    created = await db_ops.create(Collections.CITY_IATA, city_dict)
    return serialize_doc(created)

@router.get("/city-iata", response_model=List[CityIATAResponse])
async def get_city_iatas(
    is_active: bool = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all city registries"""
    filter_query = {}
    if is_active is not None:
        filter_query["is_active"] = is_active
    cities = await db_ops.get_all(Collections.CITY_IATA, filter_query)
    return serialize_docs(cities)

@router.get("/city-iata/{city_id}", response_model=CityIATAResponse)
async def get_city_iata(
    city_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get city registry by ID"""
    city = await db_ops.get_by_id(Collections.CITY_IATA, city_id)
    if not city:
        raise HTTPException(status_code=404, detail="City IATA not found")
    return serialize_doc(city)

@router.put("/city-iata/{city_id}", response_model=CityIATAResponse)
async def update_city_iata(
    city_id: str,
    city_update: CityIATAUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update city registry"""
    update_data = city_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await db_ops.update(Collections.CITY_IATA, city_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="City IATA not found")
    return serialize_doc(updated)

@router.delete("/city-iata/{city_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_city_iata(
    city_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete city registry"""
    deleted = await db_ops.delete(Collections.CITY_IATA, city_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="City IATA not found")

# ============================================================================
# 12. BOOKING EXPIRY ENDPOINTS
# ============================================================================

@router.post("/booking-expiry", response_model=BookingExpiryResponse, status_code=status.HTTP_201_CREATED)
async def create_booking_expiry(
    expiry: BookingExpiryCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create booking expiry settings"""
    expiry_dict = expiry.model_dump()
    created = await db_ops.create(Collections.BOOKING_EXPIRY, expiry_dict)
    return serialize_doc(created)

@router.get("/booking-expiry", response_model=List[BookingExpiryResponse])
async def get_booking_expiries(current_user: dict = Depends(get_current_user)):
    """Get all booking expiry configurations"""
    expiries = await db_ops.get_all(Collections.BOOKING_EXPIRY, {})
    return serialize_docs(expiries)

@router.get("/booking-expiry/active", response_model=BookingExpiryResponse)
async def get_active_booking_expiry(current_user: dict = Depends(get_current_user)):
    """Get the most recent (active) booking expiry configuration"""
    expiries = await db_ops.get_all(Collections.BOOKING_EXPIRY, {}, limit=100)
    if not expiries:
        raise HTTPException(status_code=404, detail="No booking expiry configuration found")
    # Sort by created_at in Python (most recent first)
    expiries_sorted = sorted(expiries, key=lambda x: x.get('created_at', datetime.min), reverse=True)
    return serialize_doc(expiries_sorted[0])

@router.put("/booking-expiry/{expiry_id}", response_model=BookingExpiryResponse)
async def update_booking_expiry(
    expiry_id: str,
    expiry_update: BookingExpiryUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update booking expiry settings"""
    update_data = expiry_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await db_ops.update(Collections.BOOKING_EXPIRY, expiry_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Booking expiry not found")
    return serialize_doc(updated)

@router.delete("/booking-expiry/{expiry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_booking_expiry(
    expiry_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete booking expiry configuration"""
    deleted = await db_ops.delete(Collections.BOOKING_EXPIRY, expiry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Booking expiry not found")

# ============================================================================
# 13. FILE UPLOAD ENDPOINTS
# ============================================================================
from fastapi import UploadFile, File
import shutil
import os
import uuid
from app.config.settings import settings

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload a file and return its URL"""
    try:
        # Create unique filename
        file_ext = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(settings.UPLOAD_DIR, filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Return URL (assuming server is running on localhost:8000 for now, 
        # normally would use a configurable base URL)
        # For simplicity, we return the relative path which frontend can append base URL to
        url = f"/uploads/{filename}" 
        
        return {"url": url, "filename": filename}
    except Exception as e:
        print(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")
