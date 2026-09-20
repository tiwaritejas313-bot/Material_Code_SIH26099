"""
Create the collections ("tables") this app needs, with MongoDB schema
validation mirroring the Pydantic models in app/models/, plus the indexes
each collection's query patterns actually use.

records: only the true ingestion-time fields are required (cpse, legacy_code,
description, source) -- Samanvay-sourced rows carry extra fields (cluster_id,
split, recipe, ...) that uploaded rows never will, so the validator stays
permissive on everything Phase 1/2/3 add after ingestion rather than forcing
one rigid shape on rows from very different sources.

common_material_groups / review_decisions / audit_log: not populated yet
(Phases 5-7 haven't been built), but created now with their real schema so
Phase 4+ work has a collection to write into rather than letting MongoDB
silently auto-create an unvalidated one on first insert.
"""
import asyncio
import pathlib
import sys

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import CollectionInvalid

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from app.config import settings

RECORDS_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["cpse", "legacy_code", "description", "source"],
        "properties": {
            "cpse": {"bsonType": "string"},
            "legacy_code": {"bsonType": "string"},
            "description": {"bsonType": "string"},
            "source": {"bsonType": "string"},
            "plant": {"bsonType": ["string", "null"]},
            "uom": {"bsonType": ["string", "null"]},
            "normalized_description": {"bsonType": ["string", "null"]},
            "category_predicted": {"bsonType": ["string", "null"]},
            "category_true": {"bsonType": ["string", "null"]},
            "attributes": {"bsonType": ["object", "null"]},
            "missing_critical": {"bsonType": ["array", "null"]},
            "record_id": {"bsonType": ["int", "long", "null"]},
            "cluster_id": {"bsonType": ["int", "long", "double", "null"]},
            "family_id": {"bsonType": ["int", "long", "double", "null"]},
            "split": {"bsonType": ["string", "null"]},
            "recipe": {"bsonType": ["string", "null"]},
            "qty": {"bsonType": ["int", "long", "double", "null"]},
            "unit_value": {"bsonType": ["double", "int", "null"]},
        },
    }
}

COMMON_MATERIAL_GROUPS_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["common_code", "category", "members", "status"],
        "properties": {
            "common_code": {"bsonType": "string"},
            "category": {"bsonType": "string"},
            "canonical_description": {"bsonType": ["string", "null"]},
            "members": {
                "bsonType": "array",
                "items": {
                    "bsonType": "object",
                    "required": ["cpse", "legacy_code", "record_id"],
                    "properties": {
                        "cpse": {"bsonType": "string"},
                        "legacy_code": {"bsonType": "string"},
                        "record_id": {"bsonType": "string"},
                    },
                },
            },
            "status": {"enum": ["active", "superseded"]},
        },
    }
}

REVIEW_DECISIONS_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["record_a_id", "record_b_id", "system_verdict", "reviewer", "action", "decided_at"],
        "properties": {
            "record_a_id": {"bsonType": "string"},
            "record_b_id": {"bsonType": "string"},
            "system_verdict": {"enum": ["SAME", "EQUIVALENT", "CONFLICT", "INSUFFICIENT_INFORMATION"]},
            "reviewer": {"bsonType": "string"},
            "action": {"enum": ["accept", "reject", "escalate"]},
            "reason": {"bsonType": ["string", "null"]},
            "decided_at": {"bsonType": "string"},
        },
    }
}

AUDIT_LOG_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["entity_type", "entity_id", "action", "actor", "timestamp"],
        "properties": {
            "entity_type": {"enum": ["record", "pair", "common_material_group"]},
            "entity_id": {"bsonType": "string"},
            "action": {"bsonType": "string"},
            "actor": {"bsonType": "string"},
            "previous_value": {},
            "new_value": {},
            "reason": {"bsonType": ["string", "null"]},
            "timestamp": {"bsonType": "string"},
        },
    }
}

USERS_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["username", "password_hash", "role", "active", "created_at"],
        "properties": {
            "username": {"bsonType": "string"},
            "password_hash": {"bsonType": "string"},
            "role": {"enum": ["admin", "viewer"]},
            "active": {"bsonType": "bool"},
            "created_at": {"bsonType": "string"},
        },
    }
}

COLLECTIONS = {
    "records": RECORDS_SCHEMA,
    "common_material_groups": COMMON_MATERIAL_GROUPS_SCHEMA,
    "review_decisions": REVIEW_DECISIONS_SCHEMA,
    "audit_log": AUDIT_LOG_SCHEMA,
    "users": USERS_SCHEMA,
}


async def main():
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]
    existing = await db.list_collection_names()

    for name, schema in COLLECTIONS.items():
        if name in existing:
            await db.command("collMod", name, validator=schema, validationLevel="moderate")
            print(f"  {name}: already existed, validator updated")
        else:
            try:
                await db.create_collection(name, validator=schema, validationLevel="moderate")
                print(f"  {name}: created with schema validation")
            except CollectionInvalid:
                print(f"  {name}: already existed (race), skipped")

    await db.records.create_index("cpse")
    await db.records.create_index("category_true")
    await db.records.create_index("category_predicted")
    await db.records.create_index("cluster_id")
    await db.records.create_index("source")
    await db.records.create_index("record_id")
    # NOT unique -- Samanvay's own synthetic code generator has a collision
    # rate high enough that ~4,500 groups of real (if synthetic) records
    # already share a (cpse, legacy_code) pair across UNRELATED materials.
    # A unique constraint would reject genuine, if messy, CPSE-style data;
    # detection + Data Quality reporting is the correct response, not a block.
    await db.records.create_index([("cpse", 1), ("legacy_code", 1)])

    await db.common_material_groups.create_index("common_code", unique=True)
    await db.common_material_groups.create_index("category")

    await db.review_decisions.create_index([("record_a_id", 1), ("record_b_id", 1)])
    await db.review_decisions.create_index("decided_at")

    await db.audit_log.create_index("entity_id")
    await db.audit_log.create_index("timestamp")

    await db.users.create_index("username", unique=True)

    print("\nIndexes created.")
    print("Collections now:", await db.list_collection_names())
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
