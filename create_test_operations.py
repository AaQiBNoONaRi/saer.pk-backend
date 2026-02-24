import asyncio
from datetime import datetime, timedelta
from app.config.database import db_config, Collections
from app.database.db_operations import DBOperations

db_ops = DBOperations()

async def create_test_operations():
    """Create test operations for demonstration"""
    await db_config.connect_db()
    
    print("\n" + "="*60)
    print("Creating Test Operations")
    print("="*60 + "\n")
    
    # Get the approved booking
    bookings = await db_ops.get_all(Collections.UMRAH_BOOKINGS, {"booking_status": "approved"})
    
    if not bookings:
        print("❌ No approved bookings found!")
        print("Please change a booking status to 'approved' first.")
        return
    
    booking = bookings[0]
    booking_id = str(booking["_id"])
    booking_ref = booking.get("booking_reference")
    
    print(f"✅ Found approved booking: {booking_ref}")
    print(f"   Passengers: {len(booking.get('passengers', []))}")
    
    # Get passenger info
    passengers = booking.get("passengers", [])
    if not passengers:
        passengers = [{
            "pax_id": "PAX001",
            "name": "Test Passenger",
            "passport_number": "AB1234567"
        }]
    
    pax = passengers[0]
    
    # Create dates
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    today_str = today.strftime("%Y-%m-%d")
    tomorrow_str = tomorrow.strftime("%Y-%m-%d")
    checkout_str = (today + timedelta(days=5)).strftime("%Y-%m-%d")
    
    agency_id = booking.get("agency_id", "AG001")
    agency_name = booking.get("agency_name", "Test Agency")
    branch_id = booking.get("branch_id")
    
    operations_created = 0
    
    # 1. Create Hotel Operation (Check-in today)
    hotel_op1 = {
        "operation_id": f"HOP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{pax.get('pax_id', 'PAX001')}",
        "booking_id": booking_id,
        "booking_reference": booking_ref,
        "pax_id": pax.get("pax_id", "PAX001"),
        "pax_name": pax.get("name", "Test Passenger"),
        "pax_passport": pax.get("passport_number", "AB1234567"),
        "hotel_id": "HTL001",
        "hotel_name": "Makkah Grand Hotel",
        "hotel_city": "Makkah",
        "check_in_date": today_str,
        "check_out_date": checkout_str,
        "status": "pending",
        "agency_id": agency_id,
        "agency_name": agency_name,
        "branch_id": branch_id,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    await db_ops.create(Collections.OPERATIONS, hotel_op1)
    operations_created += 1
    print(f"✅ Created Hotel Operation (Check-in today)")
    
    # 2. Create Hotel Operation (Check-out today)
    hotel_op2 = {
        "operation_id": f"HOP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{pax.get('pax_id', 'PAX002')}",
        "booking_id": booking_id,
        "booking_reference": booking_ref,
        "pax_id": pax.get("pax_id", "PAX002"),
        "pax_name": pax.get("name", "Another Guest"),
        "pax_passport": pax.get("passport_number", "CD9876543"),
        "hotel_id": "HTL001",
        "hotel_name": "Makkah Grand Hotel",
        "hotel_city": "Makkah",
        "check_in_date": (today - timedelta(days=3)).strftime("%Y-%m-%d"),
        "check_out_date": today_str,
        "status": "checked_in",
        "agency_id": agency_id,
        "agency_name": agency_name,
        "branch_id": branch_id,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    await db_ops.create(Collections.OPERATIONS, hotel_op2)
    operations_created += 1
    print(f"✅ Created Hotel Operation (Check-out today)")
    
    # 3. Create Transport Operation
    transport_op = {
        "operation_id": f"TOP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "booking_id": booking_id,
        "booking_reference": booking_ref,
        "transport_date": today_str,
        "pickup_time": "14:00",
        "route": "Makkah to Madina",
        "pickup_location": "Makkah Grand Hotel",
        "drop_location": "Madina Hotel",
        "passenger_count": len(passengers),
        "passengers": [{"pax_id": p.get("pax_id", "PAX001"), "name": p.get("name", "Test"), "status": "pending"} for p in passengers],
        "status": "pending",
        "vehicle_number": "KSA-1234",
        "agency_id": agency_id,
        "agency_name": agency_name,
        "branch_id": branch_id,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    await db_ops.create(Collections.OPERATIONS, transport_op)
    operations_created += 1
    print(f"✅ Created Transport Operation")
    
    # 4. Create Food Operation
    food_op = {
        "operation_id": f"FOP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "booking_id": booking_id,
        "booking_reference": booking_ref,
        "service_date": today_str,
        "meal_type": "Lunch",
        "location": "Makkah Grand Hotel",
        "passenger_count": len(passengers),
        "passengers": [{"pax_id": p.get("pax_id", "PAX001"), "name": p.get("name", "Test"), "status": "pending"} for p in passengers],
        "status": "pending",
        "agency_id": agency_id,
        "agency_name": agency_name,
        "branch_id": branch_id,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    await db_ops.create(Collections.OPERATIONS, food_op)
    operations_created += 1
    print(f"✅ Created Food Operation")
    
    # 5. Create Airport Operation
    airport_op = {
        "operation_id": f"AOP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "booking_id": booking_id,
        "booking_reference": booking_ref,
        "transfer_type": "pickup",
        "transfer_date": tomorrow_str,
        "transfer_time": "10:00",
        "airport_code": "JED",
        "airport_name": "King Abdulaziz International Airport",
        "flight_number": "SV123",
        "passenger_count": len(passengers),
        "passengers": [{"pax_id": p.get("pax_id", "PAX001"), "name": p.get("name", "Test"), "status": "pending"} for p in passengers],
        "status": "pending",
        "vehicle_number": "KSA-5678",
        "agency_id": agency_id,
        "agency_name": agency_name,
        "branch_id": branch_id,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    await db_ops.create(Collections.OPERATIONS, airport_op)
    operations_created += 1
    print(f"✅ Created Airport Operation")
    
    # 6. Create Ziyarat Operation
    ziyarat_op = {
        "operation_id": f"ZOP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "booking_id": booking_id,
        "booking_reference": booking_ref,
        "visit_date": today_str,
        "pickup_time": "09:00",
        "location": "Jabal al-Nour",
        "city": "Makkah",
        "duration_hours": 3,
        "passenger_count": len(passengers),
        "passengers": [{"pax_id": p.get("pax_id", "PAX001"), "name": p.get("name", "Test"), "status": "pending"} for p in passengers],
        "status": "pending",
        "vehicle_number": "KSA-9999",
        "agency_id": agency_id,
        "agency_name": agency_name,
        "branch_id": branch_id,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    await db_ops.create(Collections.OPERATIONS, ziyarat_op)
    operations_created += 1
    print(f"✅ Created Ziyarat Operation")
    
    print(f"\n{'='*60}")
    print(f"✅ Successfully created {operations_created} test operations!")
    print(f"{'='*60}\n")
    print("Now refresh your Daily Operations page to see the data.")
    print(f"Date filter should be set to: {today_str}")

if __name__ == "__main__":
    asyncio.run(create_test_operations())
