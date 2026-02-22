"""
Seed the default Chart of Accounts for an organisation.

Usage:
    python backend/scripts/seed_coa.py <organization_id>

This script calls the finance service directly (bypasses HTTP) so it can
be run without a running server.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config.database import db_config
from app.finance.services import seed_chart_of_accounts


async def main(org_id: str):
    await db_config.connect_db()
    result = await seed_chart_of_accounts(org_id, seeded_by="seed_script")
    print(f"✅  Seeded COA for org '{org_id}':")
    print(f"    Inserted : {result['inserted']}")
    print(f"    Skipped  : {result['skipped']}")
    await db_config.close_db()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/seed_coa.py <organization_id>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
