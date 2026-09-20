"""Phase 1 checkpoint: compute normalized_description for every record that doesn't have one yet."""
import asyncio
import pathlib
import sys

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from app.config import settings
from app.normalization import normalize

BATCH_SIZE = 2000


async def main():
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]

    cursor = db.records.find(
        {"normalized_description": {"$exists": False}}, {"description": 1}
    )
    batch, total = [], 0
    async for doc in cursor:
        batch.append(UpdateOne(
            {"_id": doc["_id"]},
            {"$set": {"normalized_description": normalize(doc["description"])}},
        ))
        if len(batch) >= BATCH_SIZE:
            await db.records.bulk_write(batch)
            total += len(batch)
            print(f"  ...{total:,} updated")
            batch = []
    if batch:
        await db.records.bulk_write(batch)
        total += len(batch)

    print(f"Done. normalized_description backfilled on {total:,} records.")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
