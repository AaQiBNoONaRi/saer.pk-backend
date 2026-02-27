"""Fix numeric contact_number values in the database"""
import asyncio
import motor.motor_asyncio

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "saerpk_db"

async def fix_contact_numbers():
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    hotels = db["hotels"]
    
    # Fix top-level contact_number (stored as number)
    result1 = await hotels.update_many(
        {"contact_number": {"$type": "number"}},
        [{"$set": {"contact_number": {"$toString": "$contact_number"}}}]
    )
    print(f"Fixed top-level contact_number: {result1.modified_count} hotels updated")
    
    # Fix contact_number inside contact_details array elements
    cursor = hotels.find({"contact_details.contact_number": {"$type": "number"}})
    count = 0
    async for hotel in cursor:
        hotel_id = hotel["_id"]
        contact_details = hotel.get("contact_details", [])
        fixed = []
        changed = False
        for cd in contact_details:
            if isinstance(cd.get("contact_number"), (int, float)):
                cd["contact_number"] = str(int(cd["contact_number"]))
                changed = True
            fixed.append(cd)
        if changed:
            await hotels.update_one({"_id": hotel_id}, {"$set": {"contact_details": fixed}})
            count += 1
    print(f"Fixed contact_details contact_number in {count} hotels")
    
    client.close()
    print("Done!")

asyncio.run(fix_contact_numbers())
