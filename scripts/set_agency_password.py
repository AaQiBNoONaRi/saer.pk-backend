"""
Script to manually set password for an existing agency
Run this from the backend directory: python scripts/set_agency_password.py
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def set_agency_password():
    # Connect to MongoDB
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["saer_pk"]
    agencies_collection = db["agencies"]
    
    # Get agency email
    email = input("Enter agency email: ")
    
    # Find agency
    agency = await agencies_collection.find_one({"email": email})
    if not agency:
        print(f"❌ Agency with email '{email}' not found!")
        return
    
    print(f"✅ Found agency: {agency['name']}")
    
    # Get new password
    password = input("Enter new password (min 6 characters): ")
    
    if len(password) < 6:
        print("❌ Password must be at least 6 characters!")
        return
    
    # Hash password
    hashed_password = pwd_context.hash(password)
    
    # Update agency
    result = await agencies_collection.update_one(
        {"_id": agency["_id"]},
        {
            "$set": {
                "hashed_password": hashed_password,
                "portal_access_enabled": True  # Also enable portal access
            }
        }
    )
    
    if result.modified_count > 0:
        print("✅ Password updated successfully!")
        print("✅ Portal access enabled!")
        print(f"\nYou can now login with:")
        print(f"  Email: {email}")
        print(f"  Password: {password}")
    else:
        print("❌ Failed to update password")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(set_agency_password())
