"""
Pax Movement & Intimation API
Track passenger locations and movements through their journey
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from typing import Dict, List, Optional
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc
from app.utils.auth import get_current_user

router = APIRouter(prefix="/pax-movement", tags=["Pax Movement"])


def determine_passenger_status(booking: dict, current_datetime: datetime) -> str:
    """
    Determine the current status of passengers in a booking
    
    Logic Flow:
    1. In Pakistan: Before departure flight
    2. In Flight: Between departure and arrival
    3. In Makkah/Madina: Based on hotel stays after arrival
    4. Exited KSA: After return flight or last hotel checkout
    
    Returns: One of ["in_pakistan", "in_flight", "in_makkah", "in_madina", "exited_ksa"]
    """
    flight = booking.get("flight", {})
    hotels = booking.get("hotels", [])
    
    # Get departure trip details
    departure_trip = flight.get("departure_trip", {})
    departure_dt_str = departure_trip.get("departure_datetime")
    arrival_dt_str = departure_trip.get("arrival_datetime")
    arrival_city = departure_trip.get("arrival_city", "").lower()
    
    # Get return trip details (might be None for one-way)
    return_trip = flight.get("return_trip")
    return_dt_str = return_trip.get("departure_datetime") if return_trip else None
    
    # Parse datetimes
    try:
        departure_dt = datetime.fromisoformat(departure_dt_str.replace('Z', '+00:00')) if departure_dt_str else None
        arrival_dt = datetime.fromisoformat(arrival_dt_str.replace('Z', '+00:00')) if arrival_dt_str else None
        return_dt = datetime.fromisoformat(return_dt_str.replace('Z', '+00:00')) if return_dt_str else None
    except (ValueError, AttributeError):
        # If date parsing fails, default to in_pakistan
        return "in_pakistan"
    
    # Rule 1: In Pakistan (before departure)
    if departure_dt and current_datetime < departure_dt:
        return "in_pakistan"
    
    # Rule 2: In Flight (between departure and arrival)
    if departure_dt and arrival_dt and departure_dt <= current_datetime < arrival_dt:
        return "in_flight"
    
    # Rule 3: Check if Exited KSA
    # Scenario A: Has return ticket
    if return_dt and current_datetime >= return_dt:
        return "exited_ksa"
    
    # Scenario B: No return ticket - check last hotel checkout
    if not return_dt and hotels:
        hotel_checkouts = []
        for hotel in hotels:
            checkout_str = hotel.get("check_out")
            if checkout_str:
                try:
                    # Parse date (format: YYYY-MM-DD)
                    checkout_dt = datetime.strptime(checkout_str, "%Y-%m-%d")
                    hotel_checkouts.append(checkout_dt)
                except ValueError:
                    continue
        
        if hotel_checkouts:
            latest_checkout = max(hotel_checkouts)
            # Add 23:59:59 to the checkout date for full day comparison
            latest_checkout = latest_checkout.replace(hour=23, minute=59, second=59)
            if current_datetime >= latest_checkout:
                return "exited_ksa"
    
    # Rule 4: In KSA - Determine if in Makkah or Madina
    if arrival_dt and current_datetime >= arrival_dt:
        # Check hotel stays
        for hotel in hotels:
            check_in_str = hotel.get("check_in")
            check_out_str = hotel.get("check_out")
            city = hotel.get("city", "").lower()
            
            if check_in_str and check_out_str:
                try:
                    # Parse dates
                    check_in_dt = datetime.strptime(check_in_str, "%Y-%m-%d")
                    check_out_dt = datetime.strptime(check_out_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                    
                    # Check if current time is within this hotel stay
                    if check_in_dt <= current_datetime <= check_out_dt:
                        # Determine city
                        if "makkah" in city or "makka" in city or "mecca" in city:
                            return "in_makkah"
                        elif "madina" in city or "madinah" in city or "medina" in city:
                            return "in_madina"
                except ValueError:
                    continue
        
        # Fallback: No hotel match, use arrival city
        if "makkah" in arrival_city or "makka" in arrival_city or "mecca" in arrival_city:
            return "in_makkah"
        elif "madina" in arrival_city or "madinah" in arrival_city or "medina" in arrival_city:
            return "in_madina"
        
        # Default to Makkah if in KSA but city unclear
        return "in_makkah"
    
    # Default fallback
    return "in_pakistan"


@router.get("/stats")
async def get_pax_movement_stats(current_user: dict = Depends(get_current_user)):
    """
    Get Pax Movement statistics
    Returns counts for: Total Passengers, In Pakistan, In Flight, In Makkah, In Madina, Exited KSA
    """
    try:
        # Get current datetime
        current_datetime = datetime.utcnow()
        
        # Initialize counters
        stats = {
            "total_passengers": 0,
            "in_pakistan": 0,
            "in_flight": 0,
            "in_makkah": 0,
            "in_madina": 0,
            "exit_pending": 0,  # Not used in current logic, keeping for UI compatibility
            "exited_ksa": 0
        }
        
        # Build query based on user role
        query = {"booking_status": "approved"}
        
        # Filter by agency if user is an agency
        if current_user.get("role") == "agency":
            query["agency_id"] = current_user.get("agency_id")
        elif current_user.get("role") == "branch":
            query["branch_id"] = current_user.get("branch_id")
        
        # Fetch all approved bookings (Umrah and Custom)
        umrah_bookings = await db_ops.get_all(Collections.UMRAH_BOOKINGS, query)
        custom_bookings = await db_ops.get_all(Collections.CUSTOM_BOOKINGS, query)
        
        all_bookings = list(umrah_bookings) + list(custom_bookings)
        
        # Process each booking
        for booking in all_bookings:
            # Get passenger count
            passengers = booking.get("passengers", [])
            pax_count = len(passengers)
            
            if pax_count == 0:
                continue
            
            # Determine status
            status = determine_passenger_status(booking, current_datetime)
            
            # Update counters
            stats["total_passengers"] += pax_count
            
            if status == "in_pakistan":
                stats["in_pakistan"] += pax_count
            elif status == "in_flight":
                stats["in_flight"] += pax_count
            elif status == "in_makkah":
                stats["in_makkah"] += pax_count
            elif status == "in_madina":
                stats["in_madina"] += pax_count
            elif status == "exited_ksa":
                stats["exited_ksa"] += pax_count
        
        return stats
        
    except Exception as e:
        print(f"Error getting pax movement stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/passengers")
async def get_pax_movement_list(
    status: Optional[str] = None,
    city: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Get detailed list of passengers with their current status and location
    Supports filtering by status, city, and search query
    """
    try:
        current_datetime = datetime.utcnow()
        
        # Build query
        query = {"booking_status": "approved"}
        
        # Filter by user role
        if current_user.get("role") == "agency":
            query["agency_id"] = current_user.get("agency_id")
        elif current_user.get("role") == "branch":
            query["branch_id"] = current_user.get("branch_id")
        
        # Fetch bookings
        umrah_bookings = await db_ops.get_all(Collections.UMRAH_BOOKINGS, query)
        custom_bookings = await db_ops.get_all(Collections.CUSTOM_BOOKINGS, query)
        all_bookings = list(umrah_bookings) + list(custom_bookings)
        
        passengers_list = []
        
        for booking in all_bookings:
            booking_status = determine_passenger_status(booking, current_datetime)
            passengers = booking.get("passengers", [])
            
            for passenger in passengers:
                # Determine current location
                location = "Pakistan"
                if booking_status == "in_flight":
                    location = "In Flight"
                elif booking_status == "in_makkah":
                    location = "Makkah"
                elif booking_status == "in_madina":
                    location = "Madina"
                elif booking_status == "exited_ksa":
                    location = "Exited KSA"
                
                # Build passenger data
                pax_data = {
                    "id": str(booking.get("_id")),
                    "pax_id": f"PAX-{str(booking.get('_id'))[-6:]}",
                    "name": f"{passenger.get('first_name', '')} {passenger.get('last_name', '')}".strip(),
                    "passport": passenger.get("passport_number", "N/A"),
                    "status": booking_status.replace("_", " ").title(),
                    "location": location,
                    "agent": booking.get("agency_name", "Unknown"),
                    "last_updated": booking.get("updated_at", booking.get("created_at", "")),
                    "booking_id": str(booking.get("_id"))
                }
                
                # Apply filters
                if status and status != "all":
                    if booking_status != status:
                        continue
                
                if city and city != "all":
                    if city.lower() not in location.lower():
                        continue
                
                if search:
                    search_lower = search.lower()
                    if not any([
                        search_lower in pax_data["name"].lower(),
                        search_lower in pax_data["passport"].lower(),
                        search_lower in pax_data["pax_id"].lower(),
                        search_lower in pax_data["agent"].lower()
                    ]):
                        continue
                
                passengers_list.append(pax_data)
        
        return {
            "passengers": passengers_list,
            "total": len(passengers_list)
        }
        
    except Exception as e:
        print(f"Error getting passenger list: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get passenger list: {str(e)}")
