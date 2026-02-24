"""
Check how many bookings exist in the database
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.database.db_operations import db_ops
from app.config.database import Collections, db_config

async def check_data():
    # Connect to database first
    await db_config.connect_db()
    
    umrah_bookings = await db_ops.get_all(Collections.UMRAH_BOOKINGS, {})
    custom_bookings = await db_ops.get_all(Collections.CUSTOM_BOOKINGS, {})
    
    umrah_list = list(umrah_bookings)
    custom_list = list(custom_bookings)
    
    print("=" * 50)
    print("Database Booking Counts")
    print("=" * 50)
    print(f"Umrah Bookings: {len(umrah_list)}")
    print(f"Custom Bookings: {len(custom_list)}")
    print(f"Total: {len(umrah_list) + len(custom_list)}")
    print("=" * 50)
    
    # Check approved bookings
    umrah_approved = [b for b in umrah_list if b.get('booking_status') == 'approved']
    custom_approved = [b for b in custom_list if b.get('booking_status') == 'approved']
    
    print(f"\nApproved Bookings:")
    print(f"  Umrah: {len(umrah_approved)}")
    print(f"  Custom: {len(custom_approved)}")
    print(f"  Total: {len(umrah_approved) + len(custom_approved)}")
    
    if len(umrah_list) + len(custom_list) == 0:
        print("\n⚠️  No bookings found in database!")
        print("This is why the Pax Movement page shows 0 for all stats.")
        print("\nTo add test data:")
        print("1. Create a booking through the agency portal")
        print("2. Make sure to approve it in the organization portal")
    else:
        print(f"\n✅ Found {len(umrah_list) + len(custom_list)} bookings")
        
        # Show booking statuses
        if umrah_list:
            print("\nUmrah Booking Statuses:")
            status_counts = {}
            for b in umrah_list:
                status = b.get('booking_status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
            for status, count in status_counts.items():
                print(f"  - {status}: {count}")
        
        # Show a sample if there are approved bookings
        if umrah_approved:
            sample = umrah_approved[0]
            print(f"\nSample Approved Booking:")
            print(f"  - ID: {sample.get('booking_reference')}")
            print(f"  - Passengers: {len(sample.get('passengers', []))}")
            print(f"  - Flight: {sample.get('flight', {}).get('departure_trip', {}).get('departure_city', 'N/A')}")

if __name__ == "__main__":
    asyncio.run(check_data())
