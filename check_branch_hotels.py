import asyncio
from app.config.database import db_config, Collections

async def main():
    await db_config.connect_db()
    
    branch_col = db_config.get_collection(Collections.BRANCHES)
    hotel_col = db_config.get_collection(Collections.HOTELS)
    
    branches = await branch_col.find().to_list(100)
    print(f"Total branches: {len(branches)}\n")
    
    for branch in branches:
        org_id = branch.get("organization_id")
        print(f"Branch: {branch.get('name')} | org_id: {org_id} (type: {type(org_id).__name__})")
        if org_id:
            from app.utils.auth import get_shared_org_ids
            shared_orgs = await get_shared_org_ids(str(org_id), "hotels")
            hotels_count = await hotel_col.count_documents({"organization_id": {"$in": shared_orgs}})
            print(f"  -> Has access to {hotels_count} hotels in orgs {shared_orgs}")
        else:
            print("  -> Has no organization_id! Will not see any hotels.")
        
    await db_config.close_db()

asyncio.run(main())
