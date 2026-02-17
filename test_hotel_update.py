"""
Direct test of hotel update operation
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime

async def test_update():
    # Connect to MongoDB
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["saerpk_db"]
    collection = db["hotels"]
    
    hotel_id = "69938426d6604695cfc7032a"
    
    print(f"\n1. Testing ObjectId conversion:")
    try:
        obj_id = ObjectId(hotel_id)
        print(f"   ✅ Successfully converted to ObjectId: {obj_id}")
        print(f"   Type: {type(obj_id)}")
    except Exception as e:
        print(f"   ❌ Failed to convert: {e}")
        return
    
    print(f"\n2. Testing find_one with ObjectId:")
    try:
        hotel = await collection.find_one({"_id": obj_id})
        if hotel:
            print(f"   ✅ Found hotel: {hotel.get('name')}")
        else:
            print(f"   ❌ Hotel not found")
            return
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    print(f"\n3. Testing find_one_and_update:")
    try:
        update_data = {"updated_at": datetime.utcnow(), "name": hotel.get('name')}
        result = await collection.find_one_and_update(
            {"_id": obj_id},
            {"$set": update_data},
            return_document=True
        )
        if result:
            print(f"   ✅ Update successful: {result.get('name')}")
        else:
            print(f"   ❌ Update returned None")
    except Exception as e:
        print(f"   ❌ Error during update: {e}")
        import traceback
        traceback.print_exc()
    
    client.close()

if __name__ == "__main__":
    asyncio.run(test_update())
