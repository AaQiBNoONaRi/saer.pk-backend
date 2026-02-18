"""
Script to check hotels in the database
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

async def check_hotels():
    # Connect to MongoDB
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["saerpk_db"]  # Correct database name
    collection = db["hotels"]
    
    # Get all hotels
    hotels = await collection.find().to_list(length=100)
    
    print(f"\nTotal hotels in database: {len(hotels)}\n")
    
    for hotel in hotels:
        hotel_id = hotel['_id']
        print(f"ID: {hotel_id} (type: {type(hotel_id).__name__})")
        print(f"ID as string: {str(hotel_id)}")
        print(f"Name: {hotel.get('name', 'N/A')}")
        print(f"City: {hotel.get('city', 'N/A')}")
        print(f"Category ID: {hotel.get('category_id', 'N/A')}")
        print(f"Prices count: {len(hotel.get('prices', []))}")
        
        # Test ObjectId lookup
        try:
            test_lookup = await collection.find_one({"_id": ObjectId(str(hotel_id))})
            print(f"✅ ObjectId lookup works: {test_lookup is not None}")
        except Exception as e:
            print(f"❌ ObjectId lookup failed: {e}")
        
        print("-" * 50)
    
    client.close()

if __name__ == "__main__":
    asyncio.run(check_hotels())
