import asyncio
import os
import sys
import json
from bson import ObjectId

# Add current directory to path if needed for imports
sys.path.append(os.getcwd())

from app.config.database import Collections, db_config
from app.database.db_operations import db_ops
from app.services.service_charge_logic import get_branch_service_charge, apply_hotel_charge, apply_package_charge

async def inspect():
    await db_config.connect_db()
    
    branch_id = "6984b0213bc9604e560d430b" # Lahore Branch
    hotel_id = "699aeca2994f30dba429e147"
    
    booking_dict = {
        "rooms_selected": [
            {
                "hotel_id": hotel_id,
                "room_type": "Double",
                "price_per_person": 10000,
                "quantity": 2
            }
        ],
        "visa_cost_pkr": 5000,
        "total_amount": 25000, 
    }
    
    rule = await get_branch_service_charge(branch_id)
    if rule:
        total_sc = 0
        
        # 1. Apply Hotel Charges
        for room in booking_dict.get('rooms_selected', []):
            base_p = room.get('price_per_person', 0)
            inclusive_p = apply_hotel_charge(base_p, rule, room.get('hotel_id'), room.get('room_type', 'sharing').lower())
            room['price_per_person'] = inclusive_p
            total_sc += (inclusive_p - base_p) * room.get('quantity', 0)
        
        # 2. Add hotel inc to total
        booking_dict['total_amount'] += total_sc 
        
        # 3. Apply Package Charge
        updated_total = booking_dict.get('total_amount', 0)
        final_total = apply_package_charge(updated_total, rule)
        total_sc += (final_total - updated_total)
        booking_dict['total_amount'] = final_total
        
        booking_dict['total_service_charge'] = total_sc
        
    print(f"Final Total Service Charge: {booking_dict.get('total_service_charge')}")
    print(f"Final Total Amount: {booking_dict['total_amount']}")
    
    # Calculation Check:
    # Hotel Increment: 400 * 2 = 800
    # Total after hotels: 25000 + 800 = 25800
    # Package Charge on 25800: +2000 = 27800
    # Total Service Charge: 800 + 2000 = 2800

if __name__ == "__main__":
    asyncio.run(inspect())
