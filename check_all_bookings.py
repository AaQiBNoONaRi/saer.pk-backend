"""
Check all booking collections
"""
import asyncio
from app.config.database import db_config, Collections
from app.database.db_operations import db_ops

async def check_data():
    await db_config.connect_db()
    
    # Get a sample agency
    agencies = await db_ops.get_all(Collections.AGENCIES, {}, limit=2)
    
    if agencies:
        for agency in agencies:
            agency_id = str(agency["_id"])
            print(f"\n{'='*60}")
            print(f"🏢 Agency: {agency.get('name', 'Unknown')}")
            print(f"   Agency ID: {agency_id}")
            print(f"{'='*60}")
            
            # Check TICKET_BOOKINGS
            ticket_bookings = await db_ops.get_all(Collections.TICKET_BOOKINGS, {"agency_id": agency_id})
            print(f"✈️  Ticket Bookings: {len(ticket_bookings)}")
            if ticket_bookings:
                for i, b in enumerate(ticket_bookings[:2], 1):
                    print(f"    #{i} - ID: {b.get('_id')}, Ref: {b.get('booking_reference')}, Status: {b.get('booking_status')}")
            
            # Check UMRAH_BOOKINGS
            umrah_bookings = await db_ops.get_all(Collections.UMRAH_BOOKINGS, {"agency_id": agency_id})
            print(f"🕌 Umrah Bookings: {len(umrah_bookings)}")
            if umrah_bookings:
                for i, b in enumerate(umrah_bookings[:2], 1):
                    print(f"    #{i} - ID: {b.get('_id')}, Ref: {b.get('booking_reference')}, Status: {b.get('booking_status')}")
            
            # Check CUSTOM_BOOKINGS
            custom_bookings = await db_ops.get_all(Collections.CUSTOM_BOOKINGS, {"agency_id": agency_id})
            print(f"📦 Custom Bookings: {len(custom_bookings)}")
            if custom_bookings:
                for i, b in enumerate(custom_bookings[:2], 1):
                    print(f"    #{i} - ID: {b.get('_id')}, Ref: {b.get('booking_reference')}, Status: {b.get('booking_status')}")
            
            total = len(ticket_bookings) + len(umrah_bookings) + len(custom_bookings)
            print(f"\n📊 TOTAL BOOKINGS: {total}")
    
    await db_config.close_db()

if __name__ == "__main__":
    asyncio.run(check_data())
