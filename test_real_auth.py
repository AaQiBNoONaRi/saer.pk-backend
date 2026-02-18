import httpx
import asyncio
import json

async def test_auth():
    # CORRECT endpoint from Postman collection
    endpoint = "https://pp-auth-api.aiqs.link/client/user/signin/initiate"
    
    payload = {
        "clientId": "6tvsrg4go69ktu9f4369tvmvi8",
        "authFlow": "USER_PASSWORD_AUTH",
        "authParameters": {
            "PASSWORD": "Preprod#1@2025",
            "USERNAME": "preprod@gmail.com"
        }
    }
    
    print(f"Testing CORRECT endpoint: {endpoint}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("-" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(endpoint, json=payload)
            print(f"\n✅ Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"\n🎉 SUCCESS!")
                print(f"Response: {json.dumps(data, indent=2)}")
                
                # Extract the ID token
                if 'data' in data and 'authenticationResult' in data['data']:
                    id_token = data['data']['authenticationResult'].get('idToken')
                    if id_token:
                        print(f"\n✅ IdToken Preview: {id_token[:50]}...")
            else:
                try:
                    error_data = response.json()
                    print(f"\nError Response: {json.dumps(error_data, indent=2)}")
                except:
                    print(f"\nResponse (text): {response.text[:500]}")
        except Exception as e:
            print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_auth())
