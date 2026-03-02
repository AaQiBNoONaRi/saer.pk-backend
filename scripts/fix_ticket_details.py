"""
One-time script: backfill ticket_details into ticket bookings that have None
"""
import asyncio
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['saerpk_db']
    bookings_col = db['ticket_bookings']
    flights_col = db['flights']

    bad = await bookings_col.find({
        'ticket_details': None,
        'ticket_id': {'$exists': True, '$ne': None}
    }).to_list(1000)

    print(f'Found {len(bad)} bookings with missing ticket_details')

    fixed = 0
    for b in bad:
        tid = b.get('ticket_id')
        if not tid:
            continue
        try:
            ticket = await flights_col.find_one({'_id': ObjectId(tid)})
            if ticket:
                ticket['_id'] = str(ticket['_id'])
                await bookings_col.update_one(
                    {'_id': b['_id']},
                    {'$set': {'ticket_details': ticket}}
                )
                fixed += 1
                print(f'  Fixed: {b.get("booking_reference")}')
            else:
                print(f'  Ticket not found for booking: {b.get("booking_reference")}')
        except Exception as e:
            print(f'  Error on {b.get("booking_reference")}: {e}')

    print(f'\nDone. Fixed {fixed}/{len(bad)} bookings.')
    client.close()

asyncio.run(main())
