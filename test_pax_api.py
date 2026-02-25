"""
Quick test to check if Pax Movement API is working and if there's data
"""
import requests
import json

API_BASE = "http://localhost:8000/api"

# Test 1: Check stats endpoint (no auth needed to test)
print("=" * 50)
print("Testing Pax Movement API")
print("=" * 50)

try:
    # You'll need a valid token - get from localStorage in browser or login first
    # For now, let's just check if the endpoint responds
    response = requests.get(f"{API_BASE}/pax-movement/stats")
    print(f"\n✅ Stats endpoint responded: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Stats data: {json.dumps(data, indent=2)}")
    elif response.status_code == 401:
        print("⚠️  401 Unauthorized - Authentication required (expected)")
        print("This is normal - the endpoint requires a valid JWT token")
    else:
        print(f"Response: {response.text}")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 50)
print("To test with authentication:")
print("1. Login to organization portal at http://localhost:5175")
print("2. Open browser console")
print("3. Run: localStorage.getItem('access_token')")
print("4. Copy the token and use it in the test script")
print("=" * 50)
