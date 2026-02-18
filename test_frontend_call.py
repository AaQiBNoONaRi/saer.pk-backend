import httpx
import asyncio
import json

async def test():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post("http://localhost:8000/api/flight-search/test-auth")
            print(f"✅ Status Code: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
