"""
Database configuration and connection management for MongoDB
"""
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

class DatabaseConfig:
    """MongoDB database configuration"""
    
    def __init__(self):
        self.MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.DATABASE_NAME = os.getenv("DATABASE_NAME", "saerpk_db")
        self.client: Optional[AsyncIOMotorClient] = None
        self.database = None
    
    async def connect_db(self):
        """Connect to MongoDB"""
        try:
            self.client = AsyncIOMotorClient(self.MONGO_URI)
            self.database = self.client[self.DATABASE_NAME]
            # Test connection
            await self.client.admin.command('ping')
            print(f"✅ Connected to MongoDB: {self.DATABASE_NAME}")
        except Exception as e:
            print(f"❌ Error connecting to MongoDB: {e}")
            raise
    
    async def close_db(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            print("✅ MongoDB connection closed")
    
    def get_collection(self, collection_name: str):
        """Get a specific collection"""
        if self.database is None:
            raise Exception("Database not connected")
        return self.database[collection_name]

# Global database instance
db_config = DatabaseConfig()

# Collection names
class Collections:
    ORGANIZATIONS = "organizations"
    BRANCHES = "branches"
    AGENCIES = "agencies"
    EMPLOYEES = "employees"
    CUSTOMERS = "customers"
    HOTELS = "hotels"
    FLIGHTS = "flights"
    TICKET_INVENTORY = "ticket_inventory"
    VISAS = "visas"
    TRANSPORT = "transport"
    FOOD = "food"
    ZIYARAT = "ziyarat"
    PACKAGES = "packages"
    BOOKINGS = "bookings"
    LEDGER = "ledger"
    OPERATIONS = "operations"
    PAYMENTS = "payments"
    ADMINS = "admins"
    
    # Others Management Collections
    RIYAL_RATES = "riyal_rates"
    SHIRKAS = "shirkas"
    SMALL_SECTORS = "small_sectors"
    BIG_SECTORS = "big_sectors"
    VISA_RATES_PEX = "visa_rates_pex"
    ONLY_VISA_RATES = "only_visa_rates"
    TRANSPORT_PRICES = "transport_prices"
    FOOD_PRICES = "food_prices"
    ZIARAT_PRICES = "ziarat_prices"
    FLIGHT_IATA = "flight_iata"
    CITY_IATA = "city_iata"
    BOOKING_EXPIRY = "booking_expiry"
    
    # Financial Collections
    DISCOUNTS = "discounts"
    COMMISSIONS = "commissions"
    SERVICE_CHARGES = "service_charges"
    
    # Content Management Collections
    BLOGS = "blogs"
    FORMS = "forms"
    # Hotel PMS Collections
    HOTEL_CATEGORIES = "hotel_categories"
    BED_TYPES = "bed_types"
    HOTEL_FLOORS = "hotel_floors"
    HOTEL_ROOMS = "hotel_rooms"
    HOTEL_ROOM_BOOKINGS = "hotel_room_bookings"
