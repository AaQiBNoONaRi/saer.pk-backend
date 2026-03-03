"""
Flight/Ticket routes
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.models.flight import FlightCreate, FlightUpdate, FlightResponse
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user, get_org_id, get_shared_org_ids
from app.services.service_charge_logic import get_branch_service_charge, apply_ticket_charge

router = APIRouter(prefix="/flights", tags=["Inventory: Flights"])

@router.post("/", response_model=FlightResponse, status_code=status.HTTP_201_CREATED)
async def create_flight(
    flight: FlightCreate,
    current_user: dict = Depends(get_current_user),
    org_id: str = Depends(get_org_id)
):
    """Create a new flight ticket block"""
    flight_dict = flight.model_dump()
    flight_dict["organization_id"] = org_id
    created_flight = await db_ops.create(Collections.FLIGHTS, flight_dict)
    return serialize_doc(created_flight)

@router.get("/", response_model=List[FlightResponse])
async def get_flights(
    airline: str = None,
    sector: str = None,
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
    org_id: str = Depends(get_org_id)
):
    shared_orgs = await get_shared_org_ids(org_id, "tickets")
    other_orgs = [oid for oid in shared_orgs if oid != org_id]
    
    # Base query: own tickets OR (shared tickets AND resalable)
    if other_orgs:
        filter_query = {
            "$or": [
                {"organization_id": org_id},
                {"organization_id": {"$in": other_orgs}, "allow_reselling": True}
            ]
        }
    else:
        filter_query = {"organization_id": org_id} if org_id else {}
        
    # Additional filters mapped into $and to avoid overwriting top-level $or
    and_conditions = []
    
    if airline:
        and_conditions.append({"departure_trip.airline": {"$regex": airline, "$options": "i"}})
    if sector:
        and_conditions.append({
            "$or": [
                {"departure_trip.departure_city": {"$regex": sector, "$options": "i"}},
                {"departure_trip.arrival_city": {"$regex": sector, "$options": "i"}}
            ]
        })
        
    if and_conditions:
        if "$or" in filter_query:
            # Wrap the existing $or inside an $and along with other conditions
            filter_query = {"$and": [
                {"$or": filter_query["$or"]},
                *and_conditions
            ]}
        else:
            filter_query["$and"] = and_conditions
            
    flights = await db_ops.get_all(Collections.FLIGHTS, filter_query, skip=skip, limit=limit)
    
    role = current_user.get("role")
    entity_type = current_user.get("entity_type")
    branch_id = current_user.get("branch_id") or (current_user.get("entity_id") if entity_type == "branch" else None)
    
    agency_type = current_user.get("agency_type")
    is_portal_user = (role == "branch") or (role == "agency" and agency_type == "area") or (entity_type == "branch")
    
    if is_portal_user and branch_id:
        rule = await get_branch_service_charge(branch_id)
        if rule:
            for flight in flights:
                flight["adult_selling"] = apply_ticket_charge(flight.get("adult_selling", 0), rule)
                flight["child_selling"] = apply_ticket_charge(flight.get("child_selling", 0), rule)
                flight["infant_selling"] = apply_ticket_charge(flight.get("infant_selling", 0), rule)

    return serialize_docs(flights)

@router.get("/{flight_id}", response_model=FlightResponse)
async def get_flight(
    flight_id: str,
    current_user: dict = Depends(get_current_user),
    org_id: str = Depends(get_org_id)
):
    """Get flight by ID"""
    flight = await db_ops.get_by_id(Collections.FLIGHTS, flight_id)
    is_super = current_user.get("role") in ("admin", "super_admin")
    
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")
        
    role = current_user.get("role")
    entity_type = current_user.get("entity_type")
    branch_id = current_user.get("branch_id") or (current_user.get("entity_id") if entity_type == "branch" else None)
    
    agency_type = current_user.get("agency_type")
    is_portal_user = (role == "branch") or (role == "agency" and agency_type == "area") or (entity_type == "branch")
    
    if is_portal_user and branch_id:
        rule = await get_branch_service_charge(branch_id)
        if rule:
            flight["adult_selling"] = apply_ticket_charge(flight.get("adult_selling", 0), rule)
            flight["child_selling"] = apply_ticket_charge(flight.get("child_selling", 0), rule)
            flight["infant_selling"] = apply_ticket_charge(flight.get("infant_selling", 0), rule)

    return serialize_doc(flight)

@router.put("/{flight_id}", response_model=FlightResponse)
async def update_flight(
    flight_id: str,
    flight_update: FlightUpdate,
    current_user: dict = Depends(get_current_user),
    org_id: str = Depends(get_org_id)
):
    """Update flight"""
    update_data = flight_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
        
    flight = await db_ops.get_by_id(Collections.FLIGHTS, flight_id)
    is_super = current_user.get("role") in ("admin", "super_admin")
    if not flight or (org_id and flight.get("organization_id") != org_id and not is_super):
        raise HTTPException(status_code=404, detail="Flight not found")

    updated_flight = await db_ops.update(Collections.FLIGHTS, flight_id, update_data)
    if not updated_flight:
        raise HTTPException(status_code=404, detail="Flight not found")
        
    return serialize_doc(updated_flight)

@router.delete("/{flight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flight(
    flight_id: str,
    current_user: dict = Depends(get_current_user),
    org_id: str = Depends(get_org_id)
):
    """Delete flight"""
    flight = await db_ops.get_by_id(Collections.FLIGHTS, flight_id)
    is_super = current_user.get("role") in ("admin", "super_admin")
    if not flight or (org_id and flight.get("organization_id") != org_id and not is_super):
        raise HTTPException(status_code=404, detail="Flight not found")

    deleted = await db_ops.delete(Collections.FLIGHTS, flight_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Flight not found")
