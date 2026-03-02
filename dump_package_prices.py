import asyncio
import os
import sys
import json
from bson import ObjectId

# Add current directory to path if needed for imports
sys.path.append(os.getcwd())

from app.config.database import Collections, db_config
from app.database.db_operations import db_ops

async def dump_prices():
    await db_config.connect_db()
    
    packages = await db_ops.get_all(Collections.PACKAGES, {})
    for pkg in packages:
        print(f"\nPackage: {pkg.get('title')} ({pkg.get('_id')})")
        print(f"Prices: {json.dumps(pkg.get('package_prices'), indent=2)}")

if __name__ == "__main__":
    asyncio.run(dump_prices())
