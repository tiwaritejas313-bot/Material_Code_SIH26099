"""
Phase 6: Common National Material Code generation + CPSE code mapping.

Triggered only by an "accept" decision (Phase 5) -- reject/escalate never
touch groups. Groups grow incrementally as more pairs get approved, using a
union-find-style merge: if a newly-accepted pair's two records already belong
to two DIFFERENT active groups, those groups are merged (one is marked
"superseded", preserving legacy-migration history per the PS's requirement)
rather than left as duplicate groups for the same true item.

The demo code (CNMC-NNNNNN) is a locally-generated identifier for this
prototype, not an officially issued Government of India code -- see the
earlier documentation's explicit warning against implying otherwise.
"""
from datetime import datetime, timezone

from bson import ObjectId
from pymongo import ReturnDocument


async def _next_common_code(db, session=None) -> str:
    counter = await db.counters.find_one_and_update(
        {"_id": "common_material_group"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
        session=session,
    )
    return f"CNMC-{counter['seq']:06d}"


def _member(doc: dict) -> dict:
    return {"cpse": doc["cpse"], "legacy_code": doc["legacy_code"], "record_id": str(doc["_id"])}


async def _sync_records_common_code(db, group: dict, session=None):
    ids = [ObjectId(m["record_id"]) for m in group["members"]]
    await db.records.update_many(
        {"_id": {"$in": ids}}, {"$set": {"common_code": group["common_code"]}}, session=session
    )


async def _handle_accept_in_session(db, doc_a: dict, doc_b: dict, session) -> tuple[dict, dict]:
    rid_a, rid_b = str(doc_a["_id"]), str(doc_b["_id"])

    group_a = await db.common_material_groups.find_one(
        {"status": "active", "members.record_id": rid_a}, session=session
    )
    group_b = await db.common_material_groups.find_one(
        {"status": "active", "members.record_id": rid_b}, session=session
    )

    if group_a and group_b and group_a["_id"] != group_b["_id"]:
        existing_ids = {m["record_id"] for m in group_a["members"]}
        merged_members = group_a["members"] + [m for m in group_b["members"] if m["record_id"] not in existing_ids]
        await db.common_material_groups.update_one(
            {"_id": group_a["_id"]}, {"$set": {"members": merged_members}}, session=session
        )
        await db.common_material_groups.update_one(
            {"_id": group_b["_id"]},
            {"$set": {"status": "superseded", "superseded_by": group_a["common_code"],
                      "superseded_at": datetime.now(timezone.utc).isoformat()}},
            session=session,
        )
        group_a["members"] = merged_members
        await _sync_records_common_code(db, group_a, session=session)
        event = {"type": "merged", "common_code": group_a["common_code"], "superseded_code": group_b["common_code"]}
        return group_a, event

    if group_a:
        is_new_member = not any(m["record_id"] == rid_b for m in group_a["members"])
        if is_new_member:
            new_member = _member(doc_b)
            await db.common_material_groups.update_one(
                {"_id": group_a["_id"]}, {"$push": {"members": new_member}}, session=session
            )
            group_a["members"].append(new_member)
        await _sync_records_common_code(db, group_a, session=session)
        event = {"type": "extended" if is_new_member else "unchanged", "common_code": group_a["common_code"]}
        return group_a, event

    if group_b:
        is_new_member = not any(m["record_id"] == rid_a for m in group_b["members"])
        if is_new_member:
            new_member = _member(doc_a)
            await db.common_material_groups.update_one(
                {"_id": group_b["_id"]}, {"$push": {"members": new_member}}, session=session
            )
            group_b["members"].append(new_member)
        await _sync_records_common_code(db, group_b, session=session)
        event = {"type": "extended" if is_new_member else "unchanged", "common_code": group_b["common_code"]}
        return group_b, event

    common_code = await _next_common_code(db, session=session)
    new_group = {
        "common_code": common_code,
        "category": doc_a.get("category_predicted") or doc_b.get("category_predicted") or "unknown",
        "canonical_description": doc_a.get("normalized_description"),
        "members": [_member(doc_a), _member(doc_b)],
        "status": "active",
    }
    result = await db.common_material_groups.insert_one(new_group, session=session)
    new_group["_id"] = result.inserted_id
    await _sync_records_common_code(db, new_group, session=session)
    event = {"type": "created", "common_code": common_code}
    return new_group, event


async def handle_accept(db, doc_a: dict, doc_b: dict) -> tuple[dict, dict]:
    """doc_a / doc_b are full record documents (need cpse, legacy_code, _id,
    category_predicted, normalized_description). Returns (group, event) --
    group is the resulting (possibly merged) active group; event describes
    what kind of grouping change just happened, for the caller to write a
    meaningful audit_log entry (Phase 7) without this module needing to know
    about the reviewer/reason, which it doesn't have.

    Wrapped in a MongoDB transaction: a merge is 2-3 separate document writes
    (update the surviving group, mark the other superseded, sync every
    member's records.common_code), and a crash between them used to leave the
    database in a half-merged state -- one group updated, its counterpart
    still "active", or records pointing at a common_code that no longer
    matches either group. Atlas's replica-set-backed transactions make this a
    real all-or-nothing operation instead."""
    client = db.client
    async with await client.start_session() as session:
        async with session.start_transaction():
            return await _handle_accept_in_session(db, doc_a, doc_b, session)


def serialize_group(group: dict) -> dict:
    group = dict(group)
    group["_id"] = str(group["_id"])
    return group
