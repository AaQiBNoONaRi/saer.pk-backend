import asyncio
from app.config.database import db_config, Collections
from app.database.db_operations import DBOperations

db_ops = DBOperations()

async def check_operations():
    """Check operations in database"""
    await db_config.connect_db()
    
    # Check operations
    operations = await db_ops.get_all(Collections.OPERATIONS, {})
    print(f"\n{'='*60}")
    print(f"Operations in Database: {len(operations)}")
    print(f"{'='*60}\n")
    
    if operations:
        for op in operations[:10]:
            print(f"Operation ID: {op.get('operation_id')}")
            print(f"  Booking ID: {op.get('booking_id')}")
            print(f"  Type: {op.get('operation_id', '')[:3]}")
            print(f"  Status: {op.get('status')}")
            print(f"  Date: {op.get('check_in_date') or op.get('visit_date') or op.get('service_date') or op.get('transport_date') or op.get('transfer_date')}")
            print()
    else:
        print("❌ No operations found!")
        print("\nTo create operations, bookings need to:")
        print("1. Have status 'approved' or 'delivered'")
        print("2. Have the create_operations_from_booking() function called")
        print("\nChecking bookings...")
        
        # Check bookings
        umrah_bookings = await db_ops.get_all(Collections.UMRAH_BOOKINGS, {})
        print(f"\nUmrah Bookings: {len(umrah_bookings)}")
        
        for booking in umrah_bookings[:5]:
            print(f"\n  Booking: {booking.get('booking_reference')}")
            print(f"    Status: {booking.get('booking_status')}")
            print(f"    Has Hotels: {len(booking.get('hotels', []))} hotels")
            print(f"    Has Passengers: {len(booking.get('passengers', []))} pax")

if __name__ == "__main__":
    asyncio.run(check_operations())
