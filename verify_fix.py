import sys
import os
from datetime import datetime

# Add the current directory to sys.path
sys.path.append(os.getcwd())

def test_flight_response():
    try:
        print("Attempting to import FlightResponse...")
        from app.models.flight import FlightResponse
        print("Import successful!")
        
        # Test data mirroring FlightResponse fields
        data = {
            "_id": "flight_123",
            "organization_id": "org_456",
            "trip_type": "One-way",
            "departure_trip": {
                "flight_type": "Non-Stop",
                "airline": "Emirates",
                "flight_number": "EK612",
                "departure_datetime": datetime.now(),
                "arrival_datetime": datetime.now(),
                "departure_city": "Dubai",
                "arrival_city": "Islamabad"
            },
            "adult_selling": 500.0,
            "adult_purchasing": 450.0,
            "total_seats": 100,
            "available_seats": 50,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        print("Attempting to instantiate FlightResponse...")
        flight = FlightResponse(**data)
        print(f"Instantiation successful! Flight ID: {flight.id}")
        
    except Exception as e:
        print(f"Verification failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_flight_response()
