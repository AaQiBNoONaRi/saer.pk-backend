"""
Clean old flight data from database
This script removes old flight documents that don't match the new schema
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

async def clean_old_flights():
    # Connect to MongoDB
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    database_name = os.getenv("DATABASE_NAME", "saerpk_db")
    
    client = AsyncIOMotorClient(mongo_uri)
    db = client[database_name]
    flights_collection = db["flights"]
    
    # Delete all old flights that don't have the new schema fields
    result = await flights_collection.delete_many({
        "group_name": {"$exists": False}
    })
    
    print(f"✅ Deleted {result.deleted_count} old flight documents")
    
    # Show remaining flights
    remaining = await flights_collection.count_documents({})
    print(f"📊 Remaining flights in database: {remaining}")
    
    client.close()

if __name__ == "__main__":
    print("🧹 Cleaning old flight data...")
    asyncio.run(clean_old_flights())
    print("✨ Done!")
