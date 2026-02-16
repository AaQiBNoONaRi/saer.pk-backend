"""
Seed script to create the first admin user for the organization portal
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.utils.auth import hash_password
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "saerpk_db")

async def seed_first_admin():
    """Create the first admin user"""
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DATABASE_NAME]
    admins_collection = db["admins"]
    organizations_collection = db["organizations"]
    
    print("🌱 Seeding first admin user...")
    
    # Check if admin already exists
    existing_admin = await admins_collection.find_one({"username": "admin"})
    if existing_admin:
        print("⚠️  Admin user already exists. Skipping...")
        return
    
    # Get the first organization (or create a default one)
    organization = await organizations_collection.find_one()
    
    if not organization:
        print("📝 Creating default organization...")
        org_doc = {
            "name": "Saer.Pk Head Office",
            "code": "SAER-HQ",
            "contact": {
                "email": "admin@saer.pk",
                "phone": "+92-300-1234567",
                "address": "Karachi, Pakistan"
            },
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        result = await organizations_collection.insert_one(org_doc)
        organization = await organizations_collection.find_one({"_id": result.inserted_id})
        print(f"✅ Created organization: {organization['name']}")
    
    # Create admin user
    admin_doc = {
        "username": "admin",
        "email": "admin@saer.pk",
        "full_name": "System Administrator",
        "organization_id": str(organization["_id"]),
        "role": "super_admin",
        "is_active": True,
        "password": hash_password("admin123"),  # Default password
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await admins_collection.insert_one(admin_doc)
    print(f"✅ Created admin user: {admin_doc['username']}")
    print(f"   Email: {admin_doc['email']}")
    print(f"   Password: admin123")
    print(f"   Role: {admin_doc['role']}")
    print(f"   Organization: {organization['name']}")
    print("\n🎉 First admin user created successfully!")
    print("⚠️  IMPORTANT: Change the default password after first login!")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(seed_first_admin())
