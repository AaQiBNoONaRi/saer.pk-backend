"""
Fix employees that have null/empty organization_id by deriving it from entity_id
when entity_type == 'organization'.

Usage (from repo root E:\saer.pk):
    # List affected employees (dry-run):
    $env:PYTHONPATH="backend"; python -m backend.scripts.fix_null_org_employees

    # Apply fix (derive org from entity_id):
    $env:PYTHONPATH="backend"; python -m backend.scripts.fix_null_org_employees --apply

    # Force a specific org ID on ALL null records (override):
    $env:PYTHONPATH="backend"; python -m backend.scripts.fix_null_org_employees --set-org <ORG_ID> --apply
"""
import asyncio
import argparse
from app.config.database import db_config, Collections


async def main(set_org_id: str = None, dry_run: bool = True):
    await db_config.connect_db()
    db = db_config.database
    coll = db[Collections.EMPLOYEES]

    # Find employees with null or empty organization_id
    query = {"$or": [
        {"organization_id": None},
        {"organization_id": ""},
        {"organization_id": {"$exists": False}}
    ]}
    null_count = await coll.count_documents(query)
    print(f"Found {null_count} employees with null/empty organization_id\n")

    cursor = coll.find(query)
    to_update = []
    async for doc in cursor:
        entity_type = doc.get("entity_type", "")
        entity_id = doc.get("entity_id", "")
        derived_org = entity_id if entity_type.lower() == "organization" else None
        print(
            f"- {doc.get('emp_id') or doc.get('email')} "
            f"(entity_type={entity_type}, entity_id={entity_id})"
            f" -> derived org: {derived_org or 'N/A'}"
        )
        to_update.append({
            "_id": doc["_id"],
            "derived_org": derived_org,
            "emp_id": doc.get("emp_id"),
            "email": doc.get("email"),
        })

    if not to_update:
        print("Nothing to fix.")
        await db_config.close_db()
        return

    if dry_run:
        print("\nDry run — no changes made. Re-run with --apply to update.")
        await db_config.close_db()
        return

    updated = 0
    skipped = 0
    from bson import ObjectId
    for emp in to_update:
        # Determine the org to set
        if set_org_id:
            target_org = set_org_id
        elif emp["derived_org"]:
            target_org = emp["derived_org"]
        else:
            print(f"  SKIP {emp.get('emp_id') or emp.get('email')} — cannot derive org (entity_type not 'organization') and no --set-org provided")
            skipped += 1
            continue

        result = await coll.update_one(
            {"_id": ObjectId(emp["_id"])},
            {"$set": {"organization_id": target_org}}
        )
        if result.modified_count:
            print(f"  UPDATED {emp.get('emp_id') or emp.get('email')} -> organization_id={target_org}")
            updated += 1
        else:
            print(f"  NO CHANGE for {emp.get('emp_id') or emp.get('email')}")

    print(f"\nDone: {updated} updated, {skipped} skipped.")
    await db_config.close_db()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fix employees with null organization_id')
    parser.add_argument('--set-org', dest='set_org', help='Force this org ID on all null records (override)')
    parser.add_argument('--apply', dest='apply', action='store_true', help='Actually apply changes (default: dry-run)')
    args = parser.parse_args()
    asyncio.run(main(set_org_id=args.set_org, dry_run=not args.apply))
