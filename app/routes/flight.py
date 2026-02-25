"""
Flight/Ticket routes
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.models.flight import FlightCreate, FlightUpdate, FlightResponse
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user

router = APIRouter(prefix="/flights", tags=["Inventory: Flights"])

@router.post("/", response_model=FlightResponse, status_code=status.HTTP_201_CREATED)
async def create_flight(
    flight: FlightCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new flight ticket block"""
    flight_dict = flight.model_dump()
    created_flight = await db_ops.create(Collections.FLIGHTS, flight_dict)
    return serialize_doc(created_flight)

@router.get("/", response_model=List[FlightResponse])
async def get_flights(
    airline: str = None,
    sector: str = None,
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get all flights with optional filtering"""
    filter_query = {}
    if airline:
        filter_query["departure_trip.airline"] = {"$regex": airline, "$options": "i"}
    if sector:
        # Search in departure or arrival city
        filter_query["$or"] = [
            {"departure_trip.departure_city": {"$regex": sector, "$options": "i"}},
            {"departure_trip.arrival_city": {"$regex": sector, "$options": "i"}}
        ]
        
    flights = await db_ops.get_all(Collections.FLIGHTS, filter_query, skip=skip, limit=limit)
    return serialize_docs(flights)

@router.get("/{flight_id}", response_model=FlightResponse)
async def get_flight(
    flight_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get flight by ID"""
    flight = await db_ops.get_by_id(Collections.FLIGHTS, flight_id)
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")
    return serialize_doc(flight)

@router.put("/{flight_id}", response_model=FlightResponse)
async def update_flight(
    flight_id: str,
    flight_update: FlightUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update flight"""
    update_data = flight_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
        
    updated_flight = await db_ops.update(Collections.FLIGHTS, flight_id, update_data)
    if not updated_flight:
        raise HTTPException(status_code=404, detail="Flight not found")
        
    return serialize_doc(updated_flight)

@router.delete("/{flight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flight(
    flight_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete flight"""
    deleted = await db_ops.delete(Collections.FLIGHTS, flight_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Flight not found")
