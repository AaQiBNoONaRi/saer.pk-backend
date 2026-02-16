
import asyncio
import os
import sys

# Ensure usage of the current directory for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config.database import db_config, Collections
from app.database.db_operations import db_ops

async def verify_data():
    print("🔍 Verifying database content...")
    try:
        await db_config.connect_db()
        
        # Count documents
        org_count = await db_ops.count(Collections.ORGANIZATIONS)
        branch_count = await db_ops.count(Collections.BRANCHES)
        agency_count = await db_ops.count(Collections.AGENCIES)
        emp_count = await db_ops.count(Collections.EMPLOYEES)
        
        print(f"🏢 Organizations: {org_count}")
        print(f"🌿 Branches: {branch_count}")
        print(f"✈️ Agencies: {agency_count}")
        print(f"👥 Employees: {emp_count}")
        
        if org_count > 0 and branch_count > 0 and agency_count > 0 and emp_count >= 3:
            print("✅ Verification SUCCESS: All core entities exist.")
        else:
            print("❌ Verification FAILED: Missing data.")
            
    except Exception as e:
        print(f"❌ Verification Error: {e}")
    finally:
        await db_config.close_db()

if __name__ == "__main__":
    asyncio.run(verify_data())
