"""
Quick script to check agency bookings and payments data
"""
import asyncio
from app.config.database import db_config, Collections
from app.database.db_operations import db_ops

async def check_data():
    await db_config.connect_db()
    
    # Get all agencies
    agencies = await db_ops.get_all(Collections.AGENCIES, {})
    print(f"\n📊 Total Agencies: {len(agencies)}")
    
    if agencies:
        agency = agencies[0]
        agency_id = str(agency["_id"])
        print(f"\n🏢 Checking Agency: {agency.get('name', 'Unknown')}")
        print(f"   Agency ID: {agency_id}")
        
        # Check bookings
        bookings = await db_ops.get_all(Collections.BOOKINGS, {"agency_id": agency_id})
        print(f"\n📋 Bookings with agency_id={agency_id}: {len(bookings)}")
        
        # Check all bookings to see structure
        all_bookings = await db_ops.get_all(Collections.BOOKINGS, {}, limit=3)
        print(f"\n📋 Sample of all bookings (first 3):")
        for i, booking in enumerate(all_bookings, 1):
            print(f"   Booking {i}:")
            print(f"      _id: {booking.get('_id')}")
            print(f"      agency_id: {booking.get('agency_id')}")
            print(f"      booking_reference: {booking.get('booking_reference')}")
            print(f"      created_at: {booking.get('created_at')}")
        
        # Check payments
        payments = await db_ops.get_all(Collections.PAYMENTS, {"agency_id": agency_id})
        print(f"\n💰 Payments with agency_id={agency_id}: {len(payments)}")
        
        # Check all payments
        all_payments = await db_ops.get_all(Collections.PAYMENTS, {}, limit=3)
        print(f"\n💰 Sample of all payments (first 3):")
        for i, payment in enumerate(all_payments, 1):
            print(f"   Payment {i}:")
            print(f"      _id: {payment.get('_id')}")
            print(f"      agency_id: {payment.get('agency_id')}")
            print(f"      booking_id: {payment.get('booking_id')}")
            print(f"      status: {payment.get('status')}")
            print(f"      payment_date: {payment.get('payment_date')}")
        
        print("\n" + "="*60)
        print("SUMMARY:")
        print(f"If you're seeing 0 counts, it means:")
        print(f"1. No bookings have agency_id = '{agency_id}'")
        print(f"2. No payments have agency_id = '{agency_id}'")
        print(f"\nThe API filters by exactly matching agency_id field.")
        print("="*60)
    
    await db_config.close_db()

if __name__ == "__main__":
    asyncio.run(check_data())
