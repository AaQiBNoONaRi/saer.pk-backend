"""
Booking Expiry Scheduler
Runs as a background asyncio task on app startup.
Every 60 seconds it queries all 3 booking collections for documents
where payment_deadline has passed AND booking_status is still active
(underprocess / pending), then bulk-updates them to 'expired'.
"""
import asyncio
import logging
from datetime import datetime, timezone

from app.config.database import db_config, Collections

logger = logging.getLogger(__name__)

# Collections to check and the field that holds the deadline
BOOKING_COLLECTIONS = [
    Collections.TICKET_BOOKINGS,
    Collections.UMRAH_BOOKINGS,
    Collections.CUSTOM_BOOKINGS,
]

# Statuses considered "still pending payment" (not yet paid / confirmed)
EXPIRABLE_STATUSES = ["underprocess", "pending"]


async def expire_overdue_bookings() -> None:
    """
    Bulk-expire all bookings whose payment_deadline is in the past
    and whose booking_status is still in EXPIRABLE_STATUSES.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    total_expired = 0
    for collection_name in BOOKING_COLLECTIONS:
        try:
            collection = db_config.get_collection(collection_name)

            result = await collection.update_many(
                {
                    "booking_status": {"$in": EXPIRABLE_STATUSES},
                    "payment_deadline": {"$lt": now_iso, "$exists": True, "$ne": None},
                },
                {
                    "$set": {
                        "booking_status": "expired",
                        "expired_at": now_iso,
                    }
                },
            )

            if result.modified_count > 0:
                logger.info(
                    "⏰ Expired %d booking(s) in '%s'",
                    result.modified_count,
                    collection_name,
                )
                total_expired += result.modified_count

        except Exception as exc:
            logger.error(
                "❌ Error expiring bookings in '%s': %s", collection_name, exc
            )

    if total_expired:
        print(f"⏰ Booking Expiry Scheduler: {total_expired} booking(s) marked as expired.")


async def run_expiry_scheduler(interval_seconds: int = 60) -> None:
    """
    Infinite loop that calls expire_overdue_bookings() every `interval_seconds`.
    Designed to be launched as an asyncio background task from the app lifespan.
    """
    print(f"🕐 Booking Expiry Scheduler started (interval: {interval_seconds}s)")
    # Run once immediately on startup to catch any already-expired bookings
    await expire_overdue_bookings()
    while True:
        await asyncio.sleep(interval_seconds)
        await expire_overdue_bookings()
