import asyncio
from app.config.database import db_config, Collections

async def main():
    await db_config.connect_db()
    
    # Get a branch
    branch_col = db_config.get_collection(Collections.BRANCHES)
    branch = await branch_col.find_one()
    print("Branch organization_id:", branch.get("organization_id") if branch else "No branch")
    
    # Get a hotel
    hotel_col = db_config.get_collection(Collections.HOTELS)
    hotels = await hotel_col.find().to_list(10)
    for h in hotels:
        print("Hotel id:", h.get("_id"), "organization_id:", h.get("organization_id"), "name:", h.get("name"))
        
    await db_config.close_db()

asyncio.run(main())
