import asyncio
import httpx
from app.config.database import db_config, Collections
from app.utils.auth import create_access_token

async def main():
    await db_config.connect_db()
    
    branch_col = db_config.get_collection(Collections.BRANCHES)
    branch = await branch_col.find_one()
    print("Testing with branch:", branch.get("name"), branch.get("email"), "org:", branch.get("organization_id"))
    
    # Create token for this branch
    token_data = {
        "sub": str(branch["_id"]),
        "email": branch["email"],
        "full_name": branch.get("name"),
        "role": "branch",
        "branch_id": str(branch["_id"]),
        "organization_id": str(branch.get("organization_id")) if branch.get("organization_id") else None,
        "branch_name": branch.get("name")
    }
    
    token = create_access_token(data=token_data)
    
    # Make request to hotels endpoint
    async with httpx.AsyncClient() as client:
        res = await client.get(
            "http://localhost:8000/api/hotels/",
            headers={"Authorization": f"Bearer {token}"}
        )
        print("Status:", res.status_code)
        print("Response:", res.json())
        
    await db_config.close_db()

asyncio.run(main())
