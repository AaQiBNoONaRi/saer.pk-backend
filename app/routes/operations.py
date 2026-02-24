"""
Daily Operations API Routes
Handles hotel check-ins, transport, food, airport transfers, ziyarat
Based on: daily_operations_guide.md
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import datetime, timedelta
from typing import Optional, List
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.auth import get_current_user
from app.utils.helpers import serialize_doc
from app.schemas.operations import (
    RoomAssignmentRequest,
    StatusUpdateRequest,
    CreateRoomMapRequest,
    DailyOperationsResponse,
    RoomMapResponse,
    OperationStatsResponse
)

router = APIRouter(prefix="/daily-operations", tags=["Daily Operations"])


# ============================================
# Helper Functions
# ============================================

async def create_operations_from_booking(booking: dict, booking_collection: str):
    """
    Auto-create operation records when a booking is approved
    This should be called when booking status changes to 'approved'
    """
    booking_id = str(booking.get("_id"))
    booking_ref = booking.get("booking_reference")
    passengers = booking.get("passengers", [])
    
    if not passengers:
        return
    
    # Extract common data
    agency_id = booking.get("agency_id")
    agency_name = booking.get("agency_name", "")
    branch_id = booking.get("branch_id")
    
    # 1. Create Hotel Operations
    hotels = booking.get("hotels", [])
    for hotel in hotels:
        hotel_id = hotel.get("hotel_id")
        hotel_name = hotel.get("hotel_name", "")
        hotel_city = hotel.get("city", "")
        check_in = hotel.get("check_in_date", "")
        check_out = hotel.get("check_out_date", "")
        
        for pax in passengers:
            hotel_op = {
                "operation_id": f"HOP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{pax.get('pax_id')}",
                "booking_id": booking_id,
                "booking_reference": booking_ref,
                "pax_id": pax.get("pax_id"),
                "pax_name": pax.get("name"),
                "pax_passport": pax.get("passport_number", ""),
                "hotel_id": hotel_id,
                "hotel_name": hotel_name,
                "hotel_city": hotel_city,
                "check_in_date": check_in,
                "check_out_date": check_out,
                "status": "pending",
                "agency_id": agency_id,
                "agency_name": agency_name,
                "branch_id": branch_id,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            await db_ops.create(Collections.OPERATIONS, hotel_op)
    
    # 2. Create Transport Operations (if transport data exists)
    transports = booking.get("transports", [])
    for transport in transports:
        transport_op = {
            "operation_id": f"TOP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "booking_id": booking_id,
            "booking_reference": booking_ref,
            "transport_date": transport.get("date", ""),
            "pickup_time": transport.get("pickup_time", ""),
            "route": transport.get("route", ""),
            "pickup_location": transport.get("pickup_location", ""),
            "drop_location": transport.get("drop_location", ""),
            "passenger_count": len(passengers),
            "passengers": [{"pax_id": p.get("pax_id"), "name": p.get("name"), "status": "pending"} for p in passengers],
            "status": "pending",
            "agency_id": agency_id,
            "agency_name": agency_name,
            "branch_id": branch_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        await db_ops.create(Collections.OPERATIONS, transport_op)
    
    # 3. Create Food Operations (if food data exists)
    food_services = booking.get("food_services", [])
    for food in food_services:
        food_op = {
            "operation_id": f"FOP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "booking_id": booking_id,
            "booking_reference": booking_ref,
            "service_date": food.get("date", ""),
            "meal_type": food.get("meal_type", ""),
            "location": food.get("location", ""),
            "passenger_count": len(passengers),
            "passengers": [{"pax_id": p.get("pax_id"), "name": p.get("name"), "status": "pending"} for p in passengers],
            "status": "pending",
            "agency_id": agency_id,
            "agency_name": agency_name,
            "branch_id": branch_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        await db_ops.create(Collections.OPERATIONS, food_op)


async def log_operation_change(operation_type: str, operation_id: str, action: str, 
                                old_value: dict, new_value: dict, user: dict):
    """Log operation changes for audit trail"""
    log_entry = {
        "log_id": f"LOG-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
        "operation_type": operation_type,
        "operation_id": operation_id,
        "action": action,
        "old_value": old_value,
        "new_value": new_value,
        "changed_by": str(user.get("_id")),
        "changed_by_name": user.get("name", ""),
        "changed_by_role": user.get("role", ""),
        "timestamp": datetime.utcnow()
    }
    await db_ops.create(Collections.OPERATIONS, log_entry)


# ============================================
# API Endpoints
# ============================================

@router.get("/stats")
async def get_operation_stats(current_user: dict = Depends(get_current_user)):
    """
    Get daily operation statistics
    Returns counts for today's/tomorrow's check-ins, check-outs, etc.
    """
    try:
        today = datetime.utcnow().date()
        tomorrow = today + timedelta(days=1)
        today_str = today.strftime("%Y-%m-%d")
        tomorrow_str = tomorrow.strftime("%Y-%m-%d")
        
        # Build base query - filter by role
        base_query = {}
        if current_user.get("role") == "agency":
            base_query["agency_id"] = current_user.get("agency_id")
        elif current_user.get("role") == "branch":
            base_query["branch_id"] = current_user.get("branch_id")
        
        # Get all operations
        all_operations = await db_ops.get_all(Collections.OPERATIONS, base_query)
        operations_list = list(all_operations)
        
        # Calculate stats
        stats = {
            "today_checkins": 0,
            "tomorrow_checkins": 0,
            "today_checkouts": 0,
            "pending_transports": 0,
            "pending_meals": 0,
            "pending_airport_transfers": 0,
            "pending_ziyarat": 0
        }
        
        for op in operations_list:
            op_id = op.get("operation_id", "")
            
            # Hotel operations
            if op_id.startswith("HOP"):
                if op.get("check_in_date") == today_str and op.get("status") == "pending":
                    stats["today_checkins"] += 1
                if op.get("check_in_date") == tomorrow_str:
                    stats["tomorrow_checkins"] += 1
                if op.get("check_out_date") == today_str:
                    stats["today_checkouts"] += 1
            
            # Transport operations
            elif op_id.startswith("TOP"):
                if op.get("status") == "pending":
                    stats["pending_transports"] += 1
            
            # Food operations
            elif op_id.startswith("FOP"):
                if op.get("status") == "pending":
                    stats["pending_meals"] += 1
            
            # Airport operations
            elif op_id.startswith("AOP"):
                if op.get("status") == "pending":
                    stats["pending_airport_transfers"] += 1
            
            # Ziyarat operations
            elif op_id.startswith("ZOP"):
                if op.get("status") == "pending":
                    stats["pending_ziyarat"] += 1
        
        return stats
        
    except Exception as e:
        print(f"Error getting operation stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/")
async def get_daily_operations(
    date: Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD)"),
    operation_type: Optional[str] = Query(None, description="Filter by type: hotel, transport, food, airport, ziyarat"),
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get daily operations for a specific date
    Returns all operations (hotel, transport, food, airport, ziyarat) for the given date
    """
    try:
        # Build query
        query = {}
        
        # Filter by role
        if current_user.get("role") == "agency":
            query["agency_id"] = current_user.get("agency_id")
        elif current_user.get("role") == "branch":
            query["branch_id"] = current_user.get("branch_id")
        
        # Filter by status
        if status:
            query["status"] = status
        
        # Get all operations
        all_operations = await db_ops.get_all(Collections.OPERATIONS, query)
        operations_list = [serialize_doc(op) for op in all_operations]
        
        # Filter by date if provided
        if date:
            filtered_ops = []
            for op in operations_list:
                op_id = op.get("operation_id", "")
                # Check date fields based on operation type
                if (op.get("check_in_date") == date or 
                    op.get("check_out_date") == date or
                    op.get("transport_date") == date or
                    op.get("service_date") == date or
                    op.get("transfer_date") == date or
                    op.get("visit_date") == date):
                    filtered_ops.append(op)
            operations_list = filtered_ops
        
        # Filter by operation type if provided
        if operation_type:
            type_prefixes = {
                "hotel": "HOP",
                "transport": "TOP",
                "food": "FOP",
                "airport": "AOP",
                "ziyarat": "ZOP"
            }
            prefix = type_prefixes.get(operation_type)
            if prefix:
                operations_list = [op for op in operations_list if op.get("operation_id", "").startswith(prefix)]
        
        # Categorize operations
        categorized = {
            "hotel_operations": [op for op in operations_list if op.get("operation_id", "").startswith("HOP")],
            "transport_operations": [op for op in operations_list if op.get("operation_id", "").startswith("TOP")],
            "food_operations": [op for op in operations_list if op.get("operation_id", "").startswith("FOP")],
            "airport_operations": [op for op in operations_list if op.get("operation_id", "").startswith("AOP")],
            "ziyarat_operations": [op for op in operations_list if op.get("operation_id", "").startswith("ZOP")]
        }
        
        return {
            "date": date or datetime.utcnow().strftime("%Y-%m-%d"),
            "total_operations": len(operations_list),
            **categorized
        }
        
    except Exception as e:
        print(f"Error getting daily operations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get operations: {str(e)}")


@router.patch("/update-status")
async def update_operation_status(
    request: StatusUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update operation status
    Handles: check-in, check-out, departure, arrival, served, etc.
    """
    try:
        # Get the operation
        operation = await db_ops.get_one(
            Collections.OPERATIONS,
            {"operation_id": request.operation_id}
        )
        
        if not operation:
            raise HTTPException(status_code=404, detail="Operation not found")
        
        # Store old values for logging
        old_status = operation.get("status")
        operation_id = str(operation["_id"])
        
        # Update status and timestamp
        update_data = {
            "status": request.new_status,
            "updated_at": datetime.utcnow()
        }
        
        # Add status-specific timestamps
        if request.new_status == "checked_in":
            update_data["checked_in_at"] = datetime.utcnow()
        elif request.new_status == "checked_out":
            update_data["checked_out_at"] = datetime.utcnow()
        elif request.new_status == "departed":
            update_data["departed_at"] = datetime.utcnow()
        elif request.new_status == "arrived":
            update_data["arrived_at"] = datetime.utcnow()
        elif request.new_status == "served":
            update_data["served_at"] = datetime.utcnow()
        elif request.new_status in ["started", "completed"]:
            if request.new_status == "started":
                update_data["started_at"] = datetime.utcnow()
            else:
                update_data["completed_at"] = datetime.utcnow()
        
        if request.notes:
            update_data["notes"] = request.new_status
        
        # Update the operation
        await db_ops.update(
            Collections.OPERATIONS,
            operation_id,
            update_data
        )
        
        # Log the change
        await log_operation_change(
            request.operation_type,
            request.operation_id,
            "status_changed",
            {"status": old_status},
            {"status": request.new_status},
            current_user
        )
        
        # If checking out, update room status in RoomMap
        if request.new_status == "checked_out" and operation.get("room_map_id"):
            room = await db_ops.get_one(
                Collections.OPERATIONS,
                {"room_map_id": operation.get("room_map_id")}
            )
            if room:
                await db_ops.update(
                    Collections.OPERATIONS,
                    str(room["_id"]),
                    {
                        "status": "dirty",  # Mark as needs cleaning
                        "current_booking_id": None,
                        "current_pax_id": None,
                        "updated_at": datetime.utcnow()
                    }
                )
        
        return {"message": "Status updated successfully", "new_status": request.new_status}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating operation status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")


@router.post("/assign-room")
async def assign_room_to_passenger(
    request: RoomAssignmentRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Assign a room to a passenger
    Links HotelOperation to RoomMap
    """
    try:
        # Get the room
        room = await db_ops.get_one(
            Collections.OPERATIONS,
            {"room_map_id": request.room_map_id}
        )
        
        if not room or not room.get("room_map_id"):
            raise HTTPException(status_code=404, detail="Room not found")
        
        if room.get("status") != "available":
            raise HTTPException(status_code=400, detail="Room is not available")
        
       # Get the hotel operation
        hotel_op = await db_ops.get_one(
            Collections.OPERATIONS,
            {"booking_id": request.booking_id, "pax_id": request.pax_id}
        )
        
        if not hotel_op:
            raise HTTPException(status_code=404, detail="Hotel operation not found")
        
        # Update hotel operation with room details
        await db_ops.update(
            Collections.OPERATIONS,
            str(hotel_op["_id"]),
            {
                "room_map_id": request.room_map_id,
                "floor_number": room.get("floor_number"),
                "room_number": room.get("room_number"),
                "bed_number": room.get("bed_number"),
                "updated_at": datetime.utcnow()
            }
        )
        
        # Update room status
        await db_ops.update(
            Collections.OPERATIONS,
            str(room["_id"]),
            {"room_map_id": request.room_map_id},
            {
                "status": "occupied",
                "current_booking_id": request.booking_id,
                "current_pax_id": request.pax_id,
                "updated_at": datetime.utcnow()
            }
        )
        
        # Log the assignment
        await log_operation_change(
            "hotel",
            hotel_op.get("operation_id"),
            "room_assigned",
            {},
            {"room_map_id": request.room_map_id},
            current_user
        )
        
        return {"message": "Room assigned successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error assigning room: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to assign room: {str(e)}")


@router.get("/rooms")
async def get_available_rooms(
    hotel_id: Optional[str] = Query(None),
    status: str = Query("available"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get room inventory
    Filter by hotel and availability status
    """
    try:
        query = {"room_map_id": {"$exists": True}}  # Only get RoomMap documents
        
        if hotel_id:
            query["hotel_id"] = hotel_id
        if status:
            query["status"] = status
        
        rooms = await db_ops.get_all(Collections.OPERATIONS, query)
        rooms_list = [serialize_doc(room) for room in rooms]
        
        return {
            "total": len(rooms_list),
            "rooms": rooms_list
        }
        
    except Exception as e:
        print(f"Error getting rooms: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get rooms: {str(e)}")


@router.post("/create-room")
async def create_room_map(
    request: CreateRoomMapRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new room in the inventory
    Admin/Organization only
    """
    try:
        # Check if user has permission
        if current_user.get("role") not in ["admin", "organization"]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        # Create room
        room_data = {
            "room_map_id": f"RM-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            **request.dict(),
            "status": "available",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        await db_ops.create(Collections.OPERATIONS, room_data)
        
        return {"message": "Room created successfully", "room_map_id": room_data["room_map_id"]}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating room: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create room: {str(e)}")
