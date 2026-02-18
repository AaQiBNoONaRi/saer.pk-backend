"""
Test hotel API endpoints
"""
import asyncio
import aiohttp

async def test_api():
    base_url = "http://localhost:8000/api/hotels/"
    hotel_id = "69938437d6604695cfc7032b"
    
    # You'll need to get a valid token - replace this with your actual token
    token = input("Enter your access token (from localStorage in browser): ")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    async with aiohttp.ClientSession() as session:
        # Test GET all hotels
        print("\n1. Testing GET all hotels:")
        async with session.get(base_url, headers=headers) as resp:
            print(f"Status: {resp.status}")
            data = await resp.json()
            print(f"Hotels count: {len(data) if isinstance(data, list) else 'Error'}")
            if isinstance(data, list) and len(data) > 0:
                print(f"First hotel ID: {data[0].get('_id')}")
        
        # Test GET single hotel
        print(f"\n2. Testing GET single hotel (ID: {hotel_id}):")
        async with session.get(f"{base_url}{hotel_id}", headers=headers) as resp:
            print(f"Status: {resp.status}")
            data = await resp.json()
            print(f"Response: {data}")

if __name__ == "__main__":
    asyncio.run(test_api())
