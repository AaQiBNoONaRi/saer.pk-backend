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
        # Check all fields to see if any are 3000
        print(f"\nAnalyzing Rule: {r.get('name')} ({r['_id']})")
        for k, v in r.items():
            if v == 3000:
                print(f"  [MATCH] {k}: {v}")
            elif isinstance(v, (int, float, str)):
                print(f"  {k}: {v}")

if __name__ == "__main__":
    asyncio.run(inspect())
