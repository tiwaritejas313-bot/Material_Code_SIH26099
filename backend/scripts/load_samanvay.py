"""
Phase 0 checkpoint: load Samanvay's records.csv + custom_gap_test_set/records.csv
into MongoDB's `records` collection.

Run from backend/: python scripts/load_samanvay.py
"""
import asyncio
import math
import pathlib
import sys

import pandas as pd
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from app.config import settings

DATASETS_ROOT = pathlib.Path(__file__).parent.parent.parent / "sih26099_datasets" / "01_ps_specific"
SAMANVAY_RECORDS = DATASETS_ROOT / "samanvay_synthetic_12k_clusters" / "records.csv"
CUSTOM_RECORDS = DATASETS_ROOT / "custom_gap_test_set" / "records.csv"


async def main():
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]

    existing = await db.records.count_documents({})
    if existing > 0:
        print(f"records collection already has {existing:,} documents. Drop it first if you want a clean reload:")
        print("  mongosh sih26099 --eval 'db.records.drop()'")
        client.close()
        return

    samanvay = pd.read_csv(SAMANVAY_RECORDS)
    samanvay["source"] = "samanvay"
    custom = pd.read_csv(CUSTOM_RECORDS)
    # custom set already has a `source` column; keep it as-is

    combined = pd.concat([samanvay, custom], ignore_index=True)

    def clean(value):
        if isinstance(value, float) and math.isnan(value):
            return None
        return value

    docs = [{k: clean(v) for k, v in row.items()} for row in combined.to_dict(orient="records")]
    result = await db.records.insert_many(docs)
    print(f"Inserted {len(result.inserted_ids):,} records "
          f"({len(samanvay):,} from samanvay + {len(custom):,} from custom_gap_test_set).")

    await db.records.create_index("cpse")
    await db.records.create_index("category_true")
    await db.records.create_index("cluster_id")
    await db.records.create_index("source")
    print("Indexes created on: cpse, category_true, cluster_id, source.")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
