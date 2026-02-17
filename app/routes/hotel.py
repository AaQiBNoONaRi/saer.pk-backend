from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from app.config.database import db_config, Collections
from app.utils.auth import get_current_user
from app.database.db_operations import db_ops
from app.utils.helpers import serialize_doc, serialize_docs
from app.models.hotel import HotelCreate, HotelUpdate, HotelResponse
from datetime import date

router = APIRouter(prefix="/hotels", tags=["Hotels"])

@router.post("/", response_model=HotelResponse, status_code=status.HTTP_201_CREATED)
async def create_hotel(
    hotel: HotelCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new hotel with validation rules"""
    hotel_dict = hotel.model_dump(mode='json')
    
    # Ensure dates are strings for MongoDB (Motor can't encode datetime.date)
    for key, value in hotel_dict.items():
        if isinstance(value, date):
            hotel_dict[key] = value.isoformat()
        elif key == "prices" and isinstance(value, list):
            for price in value:
                if isinstance(price.get("date_from"), date):
                    price["date_from"] = price["date_from"].isoformat()
                if isinstance(price.get("date_to"), date):
                    price["date_to"] = price["date_to"].isoformat()
    
    created = await db_ops.create(Collections.HOTELS, hotel_dict)
    return serialize_doc(created)

@router.get("/", response_model=List[HotelResponse])
async def get_hotels(
    city: str = None,
    category_id: str = None,
    available_from: date = None,
    available_until: date = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all hotels with optional filtering"""
    filter_query = {}
    
    if city:
        # Case insensitive search
        filter_query["city"] = {"$regex": city, "$options": "i"}
        
    if category_id:
        filter_query["category_id"] = category_id
        
    # Date availability check logic could be complex. 
    # For now, simplistic check: hotel availability covers requested range
    if available_from and available_until:
        filter_query["available_from"] = {"$lte": available_from.isoformat()}
        filter_query["available_until"] = {"$gte": available_until.isoformat()}
        
    hotels = await db_ops.get_all(Collections.HOTELS, filter_query)
    
    # Enrichment (Optional: Populate category name)
    # This loop could be optimized with aggregation pipeline in future
    results = []
    for hotel in hotels:
        if hotel.get("category_id"):
             category = await db_ops.get_by_id(Collections.HOTEL_CATEGORIES, hotel["category_id"])
             if category:
                 hotel["category_name"] = category.get("name")
        results.append(hotel)
        
    return serialize_docs(results)

@router.get("/{hotel_id}", response_model=HotelResponse)
async def get_hotel(
    hotel_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get hotel by ID"""
    print(f"GET request for hotel ID: {hotel_id}")
    hotel = await db_ops.get_by_id(Collections.HOTELS, hotel_id)
    if not hotel:
        print(f"Hotel {hotel_id} not found in database")
        raise HTTPException(status_code=404, detail="Hotel not found")
        
    # Populate category name
    if hotel.get("category_id"):
        category = await db_ops.get_by_id(Collections.HOTEL_CATEGORIES, hotel["category_id"])
        if category:
            hotel["category_name"] = category.get("name")
            
    return serialize_doc(hotel)

@router.put("/{hotel_id}", response_model=HotelResponse)
async def update_hotel(
    hotel_id: str,
    hotel_update: HotelUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update hotel details"""
    print(f"Attempting to update hotel with ID: {hotel_id}")
    update_data = hotel_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
        
    # Convert date objects to ISO strings for MongoDB (Motor can't encode datetime.date)
    for key, value in update_data.items():
        if isinstance(value, date):
            update_data[key] = value.isoformat()
        elif key == "prices" and isinstance(value, list):
            # Convert dates in price periods
            for price in value:
                if isinstance(price.get("date_from"), date):
                    price["date_from"] = price["date_from"].isoformat()
                if isinstance(price.get("date_to"), date):
                    price["date_to"] = price["date_to"].isoformat()
    
    updated = await db_ops.update(Collections.HOTELS, hotel_id, update_data)
    if not updated:
        print(f"Hotel {hotel_id} not found in database")
        raise HTTPException(status_code=404, detail="Hotel not found")
    return serialize_doc(updated)

@router.delete("/{hotel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hotel(
    hotel_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete hotel"""
    # Validation constraint: Cannot delete if active bookings exist (Future)
    # bookings = await db.bookings.count({hotel_id: hotel_id, status: active}) ...
    
    # Also restrict if Floors/Rooms exist? 
    # Usually cascade delete or block. For now, block if rooms exist.
    rooms = await db_ops.get_all(Collections.HOTEL_ROOMS, {"hotel_id": hotel_id}, limit=1)
    if rooms:
         raise HTTPException(
            status_code=400, 
            detail="Cannot delete hotel because it has rooms configured. Delete rooms/floors first."
        )

    deleted = await db_ops.delete(Collections.HOTELS, hotel_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Hotel not found")
