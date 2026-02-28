import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import sys

async def check():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['saerpk_db']  
    
    agencies = await db['agencies'].find({}).to_list(10)
    for a in agencies:
        print(f"Agency: {a.get('name')}, Type: {a.get('agency_type')}")
        sys.stdout.flush()

    tickets = await db['ticket_bookings'].find({}).to_list(10)
    for t in tickets:
        ad = t.get('agency_details', {})
        t_type = ad.get('agency_type') if isinstance(ad, dict) else ad
        print(f"Ticket Ref: {t.get('booking_reference')}, Agency Type: {t_type}")
        sys.stdout.flush()
        
asyncio.run(check())
