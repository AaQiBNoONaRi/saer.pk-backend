
import asyncio
import os
import sys

# Ensure usage of the current directory for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config.database import db_config, Collections
from app.database.db_operations import db_ops
from app.utils.auth import hash_password

async def seed_data():
    print("🌱 Starting database seeding...")
    
    try:
        await db_config.connect_db()
        
        # 1. Create Organization
        org_data = {
            "name": "Saerpk HQ",
            "email": "admin@saerpk.com",
            "phone": "+923001234567",
            "address": "123 Main Blvd",
            "city": "Lahore",
            "country": "Pakistan",
            "license_number": "LIC-2024-001",
            "is_active": True
        }
        
        # Check if exists
        existing_org = await db_ops.get_one(Collections.ORGANIZATIONS, {"email": org_data["email"]})
        if existing_org:
            org_id = str(existing_org["_id"])
            print(f"⚠️ Organization already exists: {org_data['name']}")
        else:
            created_org = await db_ops.create(Collections.ORGANIZATIONS, org_data)
            org_id = str(created_org["_id"])
            print(f"✅ Created Organization: {org_data['name']}")

        # 2. Create Branch
        branch_data = {
            "organization_id": org_id,
            "name": "Lahore Branch",
            "email": "lahore@saerpk.com",
            "phone": "+924231234567",
            "address": "45 Liberty Market",
            "city": "Lahore",
            "country": "Pakistan",
            "is_active": True
        }
        
        existing_branch = await db_ops.get_one(Collections.BRANCHES, {"email": branch_data["email"]})
        if existing_branch:
            branch_id = str(existing_branch["_id"])
            print(f"⚠️ Branch already exists: {branch_data['name']}")
        else:
            created_branch = await db_ops.create(Collections.BRANCHES, branch_data)
            branch_id = str(created_branch["_id"])
            print(f"✅ Created Branch: {branch_data['name']}")

        # 3. Create Agency
        agency_data = {
            "organization_id": org_id,
            "branch_id": branch_id,
            "name": "Alpha Travels",
            "email": "alpha@agency.com",
            "phone": "+923219876543",
            "address": "786 Gulberg",
            "city": "Lahore",
            "country": "Pakistan",
            "credit_limit": 100000.0,
            "credit_used": 0.0,
            "is_active": True
        }
        
        existing_agency = await db_ops.get_one(Collections.AGENCIES, {"email": agency_data["email"]})
        if existing_agency:
            agency_id = str(existing_agency["_id"])
            print(f"⚠️ Agency already exists: {agency_data['name']}")
        else:
            created_agency = await db_ops.create(Collections.AGENCIES, agency_data)
            agency_id = str(created_agency["_id"])
            print(f"✅ Created Agency: {agency_data['name']}")

        # 4. Create Employees
        password = "password123"
        hashed_pwd = hash_password(password)
        
        employees = [
            {
                "emp_id": "ORGEP001",
                "entity_type": "organization",
                "entity_id": org_id,
                "name": "Super Admin",
                "email": "admin@saerpk.com",
                "phone": "+923001234567",
                "role": "admin",
                "is_active": True,
                "hashed_password": hashed_pwd
            },
            {
                "emp_id": "BREMP001",
                "entity_type": "branch",
                "entity_id": branch_id,
                "name": "Branch Manager",
                "email": "manager@saerpk.com",
                "phone": "+923007654321",
                "role": "manager",
                "is_active": True,
                "hashed_password": hashed_pwd
            },
            {
                "emp_id": "AGCEMP001",
                "entity_type": "agency",
                "entity_id": agency_id,
                "name": "Agent Smith",
                "email": "agent@agency.com",
                "phone": "+923331122334",
                "role": "agent",
                "is_active": True,
                "hashed_password": hashed_pwd
            }
        ]
        
        for emp in employees:
            existing_emp = await db_ops.get_one(Collections.EMPLOYEES, {"emp_id": emp["emp_id"]})
            if existing_emp:
                print(f"⚠️ Employee already exists: {emp['emp_id']}")
            else:
                await db_ops.create(Collections.EMPLOYEES, emp)
                print(f"✅ Created Employee: {emp['emp_id']} ({emp['role']})")
        
        print("\n🎉 Database seeding completed successfully!")
        print(f"🔑 Default Password: {password}")
        
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
    finally:
        await db_config.close_db()

if __name__ == "__main__":
    asyncio.run(seed_data())
