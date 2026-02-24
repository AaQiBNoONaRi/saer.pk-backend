"""
Daily Operations Pydantic Schemas
Request/Response schemas for operations API
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


# ============================================
# Request Schemas
# ============================================

class RoomAssignmentRequest(BaseModel):
    """Assign a passenger to a room"""
    booking_id: str
    pax_id: str
    room_map_id: str


class StatusUpdateRequest(BaseModel):
    """Update operation status"""
    operation_id: str
    operation_type: str  # hotel, transport, food, airport, ziyarat
    new_status: str
    pax_id: Optional[str] = None  # For individual passenger status updates
    notes: Optional[str] = None


class CreateRoomMapRequest(BaseModel):
    """Create new room in inventory"""
    hotel_id: str
    hotel_name: str
    floor_number: int
    room_number: str
    bed_number: Optional[int] = None
    capacity: int = 1
    room_type: str
    notes: Optional[str] = None


# ============================================
# Response Schemas
# ============================================

class PassengerStatus(BaseModel):
    """Passenger status in operations"""
    pax_id: str
    name: str
    passport: str
    status: str


class HotelOperationResponse(BaseModel):
    """Hotel operation details"""
    operation_id: str
    booking_reference: str
    pax_name: str
    pax_passport: str
    hotel_name: str
    hotel_city: str
    check_in_date: str
    check_out_date: str
    room_number: Optional[str] = None
    bed_number: Optional[int] = None
    status: str
    agency_name: str
    created_at: datetime


class DailyOperationsResponse(BaseModel):
    """Aggregated daily operations data"""
    date: str
    stats: dict  # Counts for check-ins, check-outs, etc.
    hotel_operations: List[HotelOperationResponse]
    transport_operations: List[dict]
    food_operations: List[dict]
    airport_operations: List[dict]
    ziyarat_operations: List[dict]


class RoomMapResponse(BaseModel):
    """Room inventory details"""
    room_map_id: str
    hotel_name: str
    floor_number: int
    room_number: str
    bed_number: Optional[int]
    room_type: str
    status: str
    current_pax_name: Optional[str] = None
    current_booking_ref: Optional[str] = None


class OperationStatsResponse(BaseModel):
    """Daily operation statistics"""
    today_checkins: int
    tomorrow_checkins: int
    today_checkouts: int
    pending_transports: int
    pending_meals: int
    pending_airport_transfers: int
    pending_ziyarat: int
