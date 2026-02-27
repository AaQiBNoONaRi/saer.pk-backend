"""
Test the updated agency stats API
"""
import asyncio
from app.config.database import db_config
from app.routes.agency import get_agency_stats
from app.database.db_operations import db_ops
from app.config.database import Collections

async def test_stats():
    await db_config.connect_db()
    
    # Get agency with bookings
    agencies = await db_ops.get_all(Collections.AGENCIES, {})
    
    for agency in agencies:
        agency_id = str(agency["_id"])
        
        print(f"\n{'='*60}")
        print(f"🏢 Agency: {agency.get('name')}")
        print(f"   ID: {agency_id}")
        print(f"{'='*60}")
        
        # Manually calculate what we expect
        ticket_bookings = await db_ops.get_all(Collections.TICKET_BOOKINGS, {"agency_id": agency_id})
        umrah_bookings = await db_ops.get_all(Collections.UMRAH_BOOKINGS, {"agency_id": agency_id})
        custom_bookings = await db_ops.get_all(Collections.CUSTOM_BOOKINGS, {"agency_id": agency_id})
        payments = await db_ops.get_all(Collections.PAYMENTS, {"agency_id": agency_id})
        
        total = len(ticket_bookings) + len(umrah_bookings) + len(custom_bookings)
        
        print(f"\n📊 Expected Stats:")
        print(f"   Ticket Bookings: {len(ticket_bookings)}")
        print(f"   Umrah Bookings: {len(umrah_bookings)}")
        print(f"   Custom Bookings: {len(custom_bookings)}")
        print(f"   Total Bookings: {total}")
        print(f"   Total Payments: {len([p for p in payments if p.get('status') == 'approved'])}")
        
        if total > 0:
            print(f"\n✅ This agency has bookings - API should return data!")
            break
    
    await db_config.close_db()

if __name__ == "__main__":
    asyncio.run(test_stats())
