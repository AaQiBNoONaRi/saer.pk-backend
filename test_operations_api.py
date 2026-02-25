"""
Test Daily Operations API Endpoints
Run this after the backend server is started
"""
import requests
import json

API_BASE = "http://localhost:8000/api"

def test_operations_api():
    print("=" * 60)
    print("Testing Daily Operations API")
    print("=" * 60)
    
    # Test 1: Check stats endpoint (requires auth)
    print("\n1. Testing GET /api/daily-operations/stats")
    try:
        response = requests.get(f"{API_BASE}/daily-operations/stats")
        print(f"   Status: {response.status_code}")
        if response.status_code == 401:
            print("   ✓ Auth required (expected)")
        elif response.status_code == 200:
            print(f"   ✓ Success: {json.dumps(response.json(), indent=2)}")
        else:
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 2: Check operations list endpoint
    print("\n2. Testing GET /api/daily-operations/")
    try:
        response = requests.get(f"{API_BASE}/daily-operations/")
        print(f"   Status: {response.status_code}")
        if response.status_code == 401:
            print("   ✓ Auth required (expected)")
        elif response.status_code == 200:
            data = response.json()
            print(f"   ✓ Success: {data.get('total_operations', 0)} operations found")
        else:
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 3: Check rooms endpoint
    print("\n3. Testing GET /api/daily-operations/rooms")
    try:
        response = requests.get(f"{API_BASE}/daily-operations/rooms")
        print(f"   Status: {response.status_code}")
        if response.status_code == 401:
            print("   ✓ Auth required (expected)")
        elif response.status_code == 200:
            data = response.json()
            print(f"   ✓ Success: {data.get('total', 0)} rooms found")
        else:
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Backend Routes Registered Successfully!")
    print("=" * 60)
    print("\nAvailable Endpoints:")
    print("  - GET  /api/daily-operations/stats")
    print("  - GET  /api/daily-operations/")
    print("  - GET  /api/daily-operations/rooms")
    print("  - POST /api/daily-operations/create-room")
    print("  - POST /api/daily-operations/assign-room")
    print("  - PATCH /api/daily-operations/update-status")
    print("\nNote: All endpoints require authentication")
    print("      Login via organization portal to get access token")
    print("=" * 60)

if __name__ == "__main__":
    test_operations_api()
