import asyncio
import os
import sys
import json
from bson import ObjectId

# Add current directory to path if needed for imports
sys.path.append(os.getcwd())

from app.config.database import Collections, db_config
from app.database.db_operations import db_ops

async def inspect():
    await db_config.connect_db()
    
    rules = await db_ops.get_all(Collections.SERVICE_CHARGES)
    if not rules:
        print("No service charge rules found.")
        return
        
    for r in rules:
        print(f"\nRule Name: {r.get('name')}")
        print(f"Package Charge: {r.get('package_charge')}")
        print(f"Hotel Charges (Raw): {json.dumps(r.get('hotel_charges', []), indent=2, default=str)}")

if __name__ == "__main__":
    asyncio.run(inspect())
