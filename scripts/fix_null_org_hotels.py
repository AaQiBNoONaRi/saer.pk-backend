import asyncio
import argparse
import os
from app.config.database import db_config, Collections

async def main(set_org_id: str = None, dry_run: bool = True):
    await db_config.connect_db()
    db = db_config.database
    coll = db[Collections.HOTELS]

    query = {"organization_id": None}
    null_count = await coll.count_documents(query)
    print(f"Found {null_count} hotels with organization_id == null")

    cursor = coll.find(query)
    to_update = []
    async for doc in cursor:
        print(f"- {doc.get('_id')} : {doc.get('name')} (created_at={doc.get('created_at')})")
        to_update.append(doc.get('_id'))

    if set_org_id and to_update:
        if dry_run:
            print("Dry run enabled — no updates will be performed. Use --apply to perform updates.")
        else:
            result = await coll.update_many({"organization_id": None}, {"$set": {"organization_id": set_org_id}})
            print(f"Updated {result.modified_count} documents to organization_id={set_org_id}")

    await db_config.close_db()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fix hotels with null organization_id')
    parser.add_argument('--set-org', dest='set_org', help='Organization ID to set for null records')
    parser.add_argument('--apply', dest='apply', action='store_true', help='Perform updates (otherwise dry-run)')
    args = parser.parse_args()

    dry = not args.apply
    org_to_set = args.set_org

    if args.apply and not org_to_set:
        print('When using --apply you must provide --set-org ORGANIZATION_ID')
    else:
        asyncio.run(main(set_org_id=org_to_set, dry_run=dry))
