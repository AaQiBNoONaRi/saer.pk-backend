import asyncio
from app.config.database import db_config, Collections
from app.database.db_operations import db_ops
from app.utils.auth import create_access_token
import httpx

async def test():
    await db_config.connect_db()
    # get an org
    org = await db_ops.get_all(Collections.ORGANIZATIONS, limit=1)
    if not org:
        print("No orgs found")
        return
    org = org[0]
    token_data = {
        "sub": str(org["_id"]),
        "username": org.get("email"),
        "role": "organization",
        "organization_id": str(org["_id"]),
        "user_type": "organization"
    }
    token = create_access_token(data=token_data)
    print("Generated token:", token)
    
    async with httpx.AsyncClient() as client:
        # test create lead
        resp_lead = await client.post(
            "http://localhost:8000/api/leads/",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "customer_full_name": "Test",
                "contact_number": "123",
                "lead_source": "WhatsApp",
                "interested_in": "Umrah"
            }
        )
        print("Create Lead Status:", resp_lead.status_code, resp_lead.text)
        
        # test create task
        resp_task = await client.post(
            "http://localhost:8000/api/tasks/",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "task_type": "internal",
                "follow_up_date": "2026-02-25",
                "follow_up_time": "12:00",
                "description": "Test task"
            }
        )
        print("Create Task Status:", resp_task.status_code, resp_task.text)

if __name__ == "__main__":
    asyncio.run(test())
