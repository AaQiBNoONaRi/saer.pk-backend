"""
Hotel routes
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from datetime import date, datetime
from app.models.hotel import HotelCreate, HotelUpdate, HotelResponse
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user

router = APIRouter(prefix="/hotels", tags=["Inventory: Hotels"])

def convert_dates_to_strings(data: dict) -> dict:
    """Convert date objects to ISO format strings for MongoDB compatibility"""
    result = data.copy()
    
    # Convert top-level date fields
    if 'available_from' in result and isinstance(result['available_from'], date):
        result['available_from'] = result['available_from'].isoformat()
    if 'available_until' in result and isinstance(result['available_until'], date):
        result['available_until'] = result['available_until'].isoformat()
    
    # Convert date fields in prices array
    if 'prices' in result and isinstance(result['prices'], list):
        for price in result['prices']:
            if 'date_from' in price and isinstance(price['date_from'], date):
                price['date_from'] = price['date_from'].isoformat()
            if 'date_to' in price and isinstance(price['date_to'], date):
                price['date_to'] = price['date_to'].isoformat()
    
    return result

@router.post("/", response_model=HotelResponse, status_code=status.HTTP_201_CREATED)
async def create_hotel(
    hotel: HotelCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new hotel"""
    hotel_dict = hotel.model_dump()
    hotel_dict = convert_dates_to_strings(hotel_dict)
    created_hotel = await db_ops.create(Collections.HOTELS, hotel_dict)
    return serialize_doc(created_hotel)

@router.get("/", response_model=List[HotelResponse])
async def get_hotels(
    city: str = None,
    min_rating: int = None,
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get all hotels with optional filtering"""
    filter_query = {}
    if city:
        filter_query["city"] = {"$regex": city, "$options": "i"}
    if min_rating:
        filter_query["star_rating"] = {"$gte": min_rating}
        
    hotels = await db_ops.get_all(Collections.HOTELS, filter_query, skip=skip, limit=limit)
    return serialize_docs(hotels)

@router.get("/{hotel_id}", response_model=HotelResponse)
async def get_hotel(
    hotel_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get hotel by ID"""
    hotel = await db_ops.get_by_id(Collections.HOTELS, hotel_id)
    if not hotel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hotel not found"
        )
    return serialize_doc(hotel)

@router.put("/{hotel_id}", response_model=HotelResponse)
async def update_hotel(
    hotel_id: str,
    hotel_update: HotelUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update hotel"""
    update_data = hotel_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    update_data = convert_dates_to_strings(update_data)
    updated_hotel = await db_ops.update(Collections.HOTELS, hotel_id, update_data)
    if not updated_hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
        
    return serialize_doc(updated_hotel)

@router.delete("/{hotel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hotel(
    hotel_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete hotel"""
    deleted = await db_ops.delete(Collections.HOTELS, hotel_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Hotel not found")
