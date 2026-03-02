import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import sys
import json

async def check():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['saerpk_db']  
    
    t = await db['ticket_bookings'].find_one({"booking_reference": "TB-260228-KABZ"})
    print(json.dumps({
        "booking_reference": t.get("booking_reference"),
        "booking_status": t.get("booking_status"),
        "agency_id": str(t.get("agency_id")),
        "branch_id": str(t.get("branch_id")),
        "agency_details": t.get("agency_details"),
        "type": t.get("booking_type")
    }, default=str, indent=2))
        
asyncio.run(check())
