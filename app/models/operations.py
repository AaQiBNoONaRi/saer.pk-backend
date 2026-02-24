"""
Daily Operations Models
Handles hotel check-ins, transport, food, airport transfers, ziyarat operations
Based on: daily_operations_guide.md
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ============================================
# RoomMap - Inventory Master
# ============================================
class RoomMap(BaseModel):
    """Hotel Room Inventory Master"""
    hotel_id: str
    hotel_name: str
    floor_number: int
    room_number: str
    bed_number: Optional[int] = None  # For shared rooms
    capacity: int = 1
    room_type: str  # single, double, triple, quad
    status: str = "available"  # available, occupied, dirty, fixing
    current_booking_id: Optional[str] = None
    current_pax_id: Optional[str] = None
    last_cleaned: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================
# HotelOperation - Pax Hotel Tracking
# ============================================
class HotelOperation(BaseModel):
    """Track passenger hotel check-ins and check-outs"""
    operation_id: str = Field(default_factory=lambda: f"HOP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
    booking_id: str
    booking_reference: str
    pax_id: str
    pax_name: str
    pax_passport: str
    
    hotel_id: str
    hotel_name: str
    hotel_city: str
    
    check_in_date: str  # YYYY-MM-DD
    check_out_date: str  # YYYY-MM-DD
    
    # Room Assignment
    room_map_id: Optional[str] = None
    floor_number: Optional[int] = None
    room_number: Optional[str] = None
    bed_number: Optional[int] = None
    
    status: str = "pending"  # pending, checked_in, checked_out
    checked_in_at: Optional[datetime] = None
    checked_out_at: Optional[datetime] = None
    
    agency_id: str
    agency_name: str
    branch_id: Optional[str] = None
    
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================
# TransportOperation - Pickup/Drop Tracking
# ============================================
class TransportOperation(BaseModel):
    """Track transport pickups and drops"""
    operation_id: str = Field(default_factory=lambda: f"TOP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
    booking_id: str
    booking_reference: str
    
    transport_date: str  # YYYY-MM-DD
    pickup_time: str  # HH:MM
    route: str  # e.g., "Jeddah Airport to Makkah Hotel"
    pickup_location: str
    drop_location: str
    
    vehicle_type: Optional[str] = None  # bus, coaster, hiace, car
    vehicle_number: Optional[str] = None
    driver_name: Optional[str] = None
    driver_contact: Optional[str] = None
    
    passenger_count: int
    passengers: List[dict] = []  # [{pax_id, name, status}]
    
    status: str = "pending"  # pending, departed, arrived, cancelled
    departed_at: Optional[datetime] = None
    arrived_at: Optional[datetime] = None
    
    agency_id: str
    agency_name: str
    branch_id: Optional[str] = None
    
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================
# FoodOperation - Meal Service Tracking
# ============================================
class FoodOperation(BaseModel):
    """Track meal service distribution"""
    operation_id: str = Field(default_factory=lambda: f"FOP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
    booking_id: str
    booking_reference: str
    
    service_date: str  # YYYY-MM-DD
    meal_type: str  # breakfast, lunch, dinner, snack
    service_time: Optional[str] = None  # HH:MM
    
    location: str  # hotel name or service point
    passenger_count: int
    passengers: List[dict] = []  # [{pax_id, name, status}]
    
    menu: Optional[str] = None
    status: str = "pending"  # pending, served, cancelled
    served_at: Optional[datetime] = None
    
    agency_id: str
    agency_name: str
    branch_id: Optional[str] = None
    
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================
# AirportOperation - Transfer Tracking
# ============================================
class AirportOperation(BaseModel):
    """Track airport transfers (pickup/drop)"""
    operation_id: str = Field(default_factory=lambda: f"AOP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
    booking_id: str
    booking_reference: str
    
    transfer_type: str  # pickup, drop
    transfer_date: str  # YYYY-MM-DD
    transfer_time: str  # HH:MM
    
    airport_code: str  # JED, MED
    airport_name: str
    flight_number: Optional[str] = None
    terminal: Optional[str] = None
    
    pickup_location: Optional[str] = None  # For drop-offs
    drop_location: Optional[str] = None  # For pickups
    
    passenger_count: int
    passengers: List[dict] = []  # [{pax_id, name, status}]
    
    vehicle_type: Optional[str] = None
    vehicle_number: Optional[str] = None
    driver_name: Optional[str] = None
    driver_contact: Optional[str] = None
    
    status: str = "pending"  # pending, arrived, not_picked, completed
    completed_at: Optional[datetime] = None
    
    agency_id: str
    agency_name: str
    branch_id: Optional[str] = None
    
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================
# ZiyaratOperation - Site Visit Tracking
# ============================================
class ZiyaratOperation(BaseModel):
    """Track guided tours and site visits"""
    operation_id: str = Field(default_factory=lambda: f"ZOP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
    booking_id: str
    booking_reference: str
    
    visit_date: str  # YYYY-MM-DD
    pickup_time: str  # HH:MM
    location: str  # Site name
    city: str  # Makkah, Madina
    
    duration_hours: Optional[float] = None
    passenger_count: int
    passengers: List[dict] = []  # [{pax_id, name, status}]
    
    guide_name: Optional[str] = None
    guide_contact: Optional[str] = None
    vehicle_type: Optional[str] = None
    vehicle_number: Optional[str] = None
    
    status: str = "pending"  # pending, started, completed, cancelled
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    agency_id: str
    agency_name: str
    branch_id: Optional[str] = None
    
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================
# OperationLog - Audit Trail
# ============================================
class OperationLog(BaseModel):
    """Audit trail for all operation changes"""
    log_id: str = Field(default_factory=lambda: f"LOG-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}")
    operation_type: str  # hotel, transport, food, airport, ziyarat, room_map
    operation_id: str
    action: str  # created, status_changed, room_assigned, updated, deleted
    
    old_value: Optional[dict] = None
    new_value: Optional[dict] = None
    
    changed_by: str  # user_id or system
    changed_by_name: Optional[str] = None
    changed_by_role: Optional[str] = None
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None
