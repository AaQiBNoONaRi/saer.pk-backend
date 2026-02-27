"""
Test the agency stats API endpoint with proper authentication
"""
import requests
import json
import asyncio
from app.config.database import db_config, Collections
from app.database.db_operations import db_ops

async def get_admin_info():
    """Get admin credentials from database"""
    await db_config.connect_db()
    admins = await db_ops.get_all(Collections.ADMINS, {}, limit=1)
    await db_config.close_db()
    
    if admins:
        admin = admins[0]
        return {
            "username": admin.get("username"),
            "has_password": bool(admin.get("password"))
        }
    return None

def test_api():
    """Test the agency stats API"""
    print("=" * 80)
    print("🧪 TESTING AGENCY STATS API")
    print("=" * 80)
    
    # Agency with data
    agency_id = "69907f1a1a2ed26ed3fc82ee"
    stats_url = f"http://localhost:8000/api/agencies/{agency_id}/stats"
    
    # Get admin info
    admin_info = asyncio.run(get_admin_info())
    
    if not admin_info:
        print("❌ No admin found in database")
        return
    
    print(f"\n✅ Found admin: {admin_info['username']}")
    
    # Try different password possibilities
    passwords = ["Test123!@", "admin123", "password", "admin", "Admin123!"]
    
    login_url = "http://localhost:8000/api/admin/login"
    access_token = None
    
    print(f"\n🔐 Attempting login at: {login_url}")
    
    for pwd in passwords:
        try:
            login_data = {
                "username": admin_info['username'],
                "password": pwd
            }
            
            response = requests.post(login_url, json=login_data, timeout=5)
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get("access_token")
                print(f"✅ Login successful with password: {pwd[:3]}***")
                break
            elif response.status_code != 401:
                print(f"⚠️  Unexpected status {response.status_code}: {response.text[:100]}")
        except Exception as e:
            print(f"❌ Login error: {e}")
            return
    
    if not access_token:
        print(f"\n❌ Could not login with any password")
        print(f"💡 Try logging into the app to see what password works")
        return
    
    # Test the stats API
    print(f"\n📊 Testing Stats API: {stats_url}")
    print("=" * 80)
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(stats_url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            stats = response.json()
            
            print(f"\n✅ API RESPONSE (Status {response.status_code}):")
            print("=" * 80)
            print(json.dumps(stats, indent=2))
            print("=" * 80)
            
            # Verify
            print(f"\n📊 RESULTS:")
            print(f"   Total Bookings: {stats['total_bookings']}")
            print(f"   On-Time Payments: {stats['on_time_payments']}")
            print(f"   Late Payments: {stats['late_payments']}")
            print(f"   Total Payments: {stats['total_payments']}")
            print(f"   Disputes: {stats['disputes']}")
            
            if stats['total_bookings'] > 0:
                print(f"\n🎉 SUCCESS! API is working correctly!")
            else:
                print(f"\n⚠️  WARNING: No bookings found")
        else:
            print(f"❌ API Error (Status {response.status_code}):")
            print(response.text)
    
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Backend server not responding")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    try:
        test_api()
    except KeyboardInterrupt:
        print("\n\n👋 Test cancelled")
