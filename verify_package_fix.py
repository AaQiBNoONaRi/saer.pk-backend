import asyncio
import os
import sys
import json
from bson import ObjectId

# Add current directory to path if needed for imports
sys.path.append(os.getcwd())

from app.config.database import Collections, db_config
from app.database.db_operations import db_ops
from app.services.service_charge_logic import get_branch_service_charge, apply_package_charge

async def inspect():
    await db_config.connect_db()
    
    branch_id = "6984b0213bc9604e560d430b" # Lahore Branch
    
    # Simulate API logic
    pkg = await db_ops.get_one(Collections.PACKAGES, {})
    if pkg:
        print(f"Original Structure: {pkg.get('package_prices')}")
        
        rule = await get_branch_service_charge(branch_id)
        if rule:
            if pkg.get("package_prices"):
                for room_type, price in pkg["package_prices"].items():
                    if isinstance(price, dict) and "selling" in price:
                        original_val = price.get("selling", 0)
                        price["selling"] = apply_package_charge(original_val, rule)
                    elif isinstance(price, (int, float)):
                        pkg["package_prices"][room_type] = {"selling": apply_package_charge(price, rule)}
            
            print(f"Fixed Structure: {pkg.get('package_prices')}")
            
            # Check if all values are dicts with 'selling'
            for k, v in pkg["package_prices"].items():
                if not (isinstance(v, dict) and "selling" in v):
                    print(f"❌ Error: {k} is still not correct: {v}")
                else:
                    print(f"✅ {k}: {v['selling']}")

if __name__ == "__main__":
    asyncio.run(inspect())
