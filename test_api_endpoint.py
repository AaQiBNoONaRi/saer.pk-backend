"""
Test the agency stats API endpoint
"""
import requests
import json

# First, let's login to get a token
login_url = "http://localhost:8000/api/admin/login"
stats_url = "http://localhost:8000/api/agencies/69907f1a1a2ed26ed3fc82ee/stats"

print("🔐 Attempting to login...")
print("=" * 80)

# Try to login (adjust credentials if needed)
login_data = {
    "username": "admin",
    "password": "Test123!@"
}

try:
    # Login
    login_response = requests.post(login_url, json=login_data)
    
    if login_response.status_code == 200:
        token_data = login_response.json()
        access_token = token_data.get("access_token")
        print(f"✅ Login successful!")
        print(f"   Token: {access_token[:20]}...")
        
        # Test the stats API
        print("\n📊 Testing Agency Stats API...")
        print("=" * 80)
        print(f"   Endpoint: {stats_url}")
        
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        stats_response = requests.get(stats_url, headers=headers)
        
        if stats_response.status_code == 200:
            stats_data = stats_response.json()
            print(f"\n✅ API Response (Status {stats_response.status_code}):")
            print("=" * 80)
            print(json.dumps(stats_data, indent=2))
            print("=" * 80)
            
            # Verify the data
            print("\n✅ VERIFICATION:")
            print(f"   Total Bookings: {stats_data['total_bookings']} (Expected: 9)")
            print(f"   On-Time Payments: {stats_data['on_time_payments']} (Expected: 3)")
            print(f"   Late Payments: {stats_data['late_payments']} (Expected: 0)")
            print(f"   Total Payments: {stats_data['total_payments']} (Expected: 3)")
            print(f"   Disputes: {stats_data['disputes']} (Expected: 0)")
            
            if stats_data['total_bookings'] == 9 and stats_data['on_time_payments'] == 3:
                print("\n🎉 SUCCESS! API is working correctly!")
            else:
                print("\n⚠️  WARNING! Numbers don't match expected values.")
        else:
            print(f"\n❌ Stats API Error (Status {stats_response.status_code}):")
            print(stats_response.text)
    else:
        print(f"❌ Login failed (Status {login_response.status_code}):")
        print(login_response.text)
        print("\n💡 Note: Make sure backend server is running and credentials are correct")

except requests.exceptions.ConnectionError:
    print("❌ Connection Error: Backend server is not running!")
    print("\n💡 Start the backend with: cd backend && python run.py")
except Exception as e:
    print(f"❌ Error: {e}")
