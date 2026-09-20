"""Phase 3 checkpoint: precompute embeddings for every record and cache to disk."""
import asyncio
import pathlib
import sys
import time

from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from app.config import settings
from app.embeddings import build_and_save_index


async def main():
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]

    ids, texts, categories = [], [], []
    async for doc in db.records.find({}, {"normalized_description": 1, "category_predicted": 1}):
        ids.append(str(doc["_id"]))
        texts.append(doc.get("normalized_description") or "")
        categories.append(doc.get("category_predicted"))

    print(f"Encoding {len(ids):,} records...")
    t0 = time.time()
    build_and_save_index(ids, texts, categories)
    print(f"Done in {time.time()-t0:.1f}s. Index cached to backend/data/.")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
