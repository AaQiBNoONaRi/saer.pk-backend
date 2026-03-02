import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
load_dotenv()

async def main():
    client = AsyncIOMotorClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017'))
    db = client[os.getenv('DATABASE_NAME', 'saerpk_db')]
    packages = await db['packages'].find({}, {'title': 1, 'package_prices': 1}).to_list(20)
    for p in packages:
        prices = p.get('package_prices', {})
        keys = list(prices.keys())
        print(f"Package: {p.get('title','?')} => keys: {keys}")
        for k, v in prices.items():
            print(f"  {k}: {v}")

asyncio.run(main())
