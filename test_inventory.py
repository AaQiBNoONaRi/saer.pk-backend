
import asyncio
import os
import sys

# Ensure usage of the current directory for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config.database import db_config, Collections
from app.database.db_operations import db_ops
from datetime import datetime

async def test_inventory():
    print("🧪 Starting Inventory Test...")
    
    try:
        await db_config.connect_db()
        
        # 1. Create Hotel
        hotel_data = {
            "name": "Makkah Royal Clock Tower",
            "city": "Makkah",
            "star_rating": 5,
            "distance_from_haram": 0.0,
            "floors": ["10", "11", "12"],
            "room_categories": [
                {
                    "type": "Quad",
                    "price": 500.0,
                    "total_capacity": 10,
                    "available_capacity": 10
                },
                {
                    "type": "Double",
                    "price": 800.0,
                    "total_capacity": 5,
                    "available_capacity": 5
                }
            ],
            "is_active": True
        }
        
        created_hotel = await db_ops.create(Collections.HOTELS, hotel_data)
        print(f"✅ Created Hotel: {created_hotel['name']}")
        
        # 2. Create Flight Block
        flight_data = {
            "airline": "Saudia",
            "pnr_reference": "SV-12345",
            "departure_date": datetime.utcnow(),
            "sector": "KHI-JED-KHI",
            "total_seats": 50,
            "available_seats": 50,
            "buying_price": 100000.0,
            "selling_price": 120000.0,
            "is_active": True
        }
        
        created_flight = await db_ops.create(Collections.FLIGHTS, flight_data)
        print(f"✅ Created Flight Block: {created_flight['pnr_reference']}")
        
        # 3. Create Transport
        transport_data = {
            "vehicle_type": "Bus",
            "capacity": 50,
            "price_per_day": 1000.0,
            "route_prices": [
                {
                    "route_name": "Jeddah to Makkah",
                    "price": 500.0
                }
            ],
            "is_active": True
        }
        
        created_transport = await db_ops.create(Collections.TRANSPORT, transport_data)
        print(f"✅ Created Transport: {created_transport['vehicle_type']}")
        
        print("\n🎉 Inventory Test Passed!")
        
    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
    finally:
        await db_config.close_db()

if __name__ == "__main__":
    asyncio.run(test_inventory())
