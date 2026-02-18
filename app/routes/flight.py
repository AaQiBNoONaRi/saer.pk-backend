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
    # Force organization_id from current user
    if current_user.get("user_type") == "organization":
        flight.organization_id = current_user.get("organization_id")
    elif not flight.organization_id:
        flight.organization_id = current_user.get("organization_id")

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
    """Get all flights with optional filtering, including shared inventory"""
    org_id = current_user.get("organization_id")

    # ── Find orgs sharing tickets with current org (active shares) ─────────
    shared_org_ids = []
    if org_id:
        active_shares = await db_ops.get_all(Collections.INVENTORY_SHARES, {
            "$and": [
                {"$or": [{"from_org_id": org_id}, {"to_org_id": org_id}]},
                {"status": "active"},
                {"inventory_types": {"$in": ["tickets"]}}
            ]
        })
        for share in active_shares:
            other = share["to_org_id"] if share["from_org_id"] == org_id else share["from_org_id"]
            if other not in shared_org_ids:
                shared_org_ids.append(other)

    # ── Build org filter: own org + shared orgs ────────────────────────────
    org_filter = []
    if org_id:
        org_filter.append({"organization_id": org_id})
    for sid in shared_org_ids:
        org_filter.append({"organization_id": sid})

    filter_query = {}
    if org_filter:
        filter_query["$or"] = org_filter

    if airline:
        filter_query["departure_trip.airline"] = {"$regex": airline, "$options": "i"}
    if sector:
        sector_filter = [
            {"departure_trip.departure_city": {"$regex": sector, "$options": "i"}},
            {"departure_trip.arrival_city": {"$regex": sector, "$options": "i"}}
        ]
        if "$or" in filter_query:
            # Combine org $or and sector $or with $and
            filter_query = {
                "$and": [
                    {"$or": filter_query.pop("$or")},
                    {"$or": sector_filter},
                    *[{k: v} for k, v in filter_query.items()]
                ]
            }
        else:
            filter_query["$or"] = sector_filter

    flights = await db_ops.get_all(Collections.FLIGHTS, filter_query, skip=skip, limit=limit)

    # ── Tag shared flights so UI can label them ────────────────────────────
    result = []
    for f in serialize_docs(flights):
        f["is_shared"] = f.get("organization_id") != org_id
        f["shared_from_org_id"] = f.get("organization_id") if f["is_shared"] else None
        result.append(f)

    return result

@router.get("/{flight_id}", response_model=FlightResponse)
async def get_flight(
    flight_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get flight by ID (own or shared)"""
    flight = await db_ops.get_by_id(Collections.FLIGHTS, flight_id)
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")

    user_org_id = current_user.get("organization_id")
    flight_org_id = flight.get("organization_id")

    if user_org_id and flight_org_id != user_org_id:
        # Check if there's an active ticket share between the two orgs
        share = await db_ops.get_one(Collections.INVENTORY_SHARES, {
            "$and": [
                {"$or": [
                    {"from_org_id": user_org_id, "to_org_id": flight_org_id},
                    {"from_org_id": flight_org_id, "to_org_id": user_org_id}
                ]},
                {"status": "active"},
                {"inventory_types": {"$in": ["tickets"]}}
            ]
        })
        if not share:
            raise HTTPException(status_code=403, detail="Not authorized to view this flight")

    result = serialize_doc(flight)
    result["is_shared"] = flight_org_id != user_org_id
    result["shared_from_org_id"] = flight_org_id if result["is_shared"] else None
    return result

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
