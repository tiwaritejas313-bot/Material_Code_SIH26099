"""Phase 2 checkpoint: compute category_predicted/attributes/missing_critical for every record."""
import asyncio
import pathlib
import sys

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from app.config import settings
from app.attributes import extract

BATCH_SIZE = 2000


async def main():
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]

    cursor = db.records.find({}, {"normalized_description": 1})
    batch, total = [], 0
    async for doc in cursor:
        result = extract(doc.get("normalized_description") or "")
        batch.append(UpdateOne({"_id": doc["_id"]}, {"$set": result}))
        if len(batch) >= BATCH_SIZE:
            await db.records.bulk_write(batch)
            total += len(batch)
            print(f"  ...{total:,} updated")
            batch = []
    if batch:
        await db.records.bulk_write(batch)
        total += len(batch)

    print(f"Done. category_predicted/attributes/missing_critical set on {total:,} records.")
    await db.records.create_index("category_predicted")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
