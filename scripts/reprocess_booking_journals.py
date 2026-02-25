"""
Reprocess existing Umrah bookings to create missing journal entries.

Usage:
    python backend/scripts/reprocess_booking_journals.py <organization_id> [--seed]

If --seed is provided the script will seed the default Chart of Accounts for the org
before attempting to create journals.
"""
import asyncio
import sys
import os
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config.database import db_config, Collections
from app.finance.services import seed_chart_of_accounts
from app.finance.journal_engine import create_umrah_booking_journal
from app.utils.helpers import serialize_doc


async def main(org_id: str, do_seed: bool = False):
    await db_config.connect_db()

    if do_seed:
        print(f"Seeding default COA for org {org_id}...")
        res = await seed_chart_of_accounts(org_id, seeded_by="reprocess_script")
        print(f"Seed result: inserted={res.get('inserted')} skipped={res.get('skipped')}")

    bookings_coll = db_config.get_collection(Collections.UMRAH_BOOKINGS)
    journals_coll = db_config.get_collection(Collections.JOURNAL_ENTRIES)

    cursor = bookings_coll.find({"organization_id": org_id})
    count = 0
    created = 0
    skipped = 0
    async for b in cursor:
        count += 1
        booking = serialize_doc(b)
        ref = booking.get('booking_reference')
        if not ref:
            print(f"Booking {booking.get('_id')} has no booking_reference — skipping")
            skipped += 1
            continue

        # check if any journal exists for this booking_reference
        existing = await journals_coll.find_one({"reference_type": "umrah_booking", "reference_id": ref})
        if existing:
            skipped += 1
            continue

        try:
            print(f"Creating journal for booking {ref} (id={booking.get('_id')})")
            await create_umrah_booking_journal(
                booking=booking,
                organization_id=org_id,
                branch_id=booking.get('branch_id'),
                agency_id=booking.get('agency_id'),
                created_by=booking.get('created_by') or 'reprocess_script',
            )
            created += 1
        except Exception as e:
            print(f"Failed to create journal for {ref}: {e}")

    print(f"Processed bookings: {count}, journals created: {created}, skipped: {skipped}")
    await db_config.close_db()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python backend/scripts/reprocess_booking_journals.py <organization_id> [--seed]")
        sys.exit(1)
    org = sys.argv[1]
    seed_flag = '--seed' in sys.argv[2:]
    asyncio.run(main(org, do_seed=seed_flag))
