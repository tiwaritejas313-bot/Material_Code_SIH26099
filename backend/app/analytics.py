"""
Phase 8 / production hardening: dashboard analytics.

get_match_status_summary is an estimate, not a verified count: it flags each
record's SINGLE best same-category embedding match and runs it through
Phase 4's actual evaluate_pair() (the same rule engine backing the review
queue and /pairs/evaluate -- not a separate ad-hoc heuristic). It will
under-count records whose critical attribute value was typo-corrupted into a
non-match (the Phase 2 extraction limitation documented earlier), and it only
checks one candidate per record, not an exhaustive pairwise scan -- so this is
a floor, not a ceiling, on the real number. Never present it as a measured
fact in the PPT/demo.
"""
from collections import defaultdict

import numpy as np

from app.compatibility import evaluate_pair
from app.embeddings import _load_index

SIMILARITY_FLOOR = 0.75


async def get_match_status_summary(db) -> dict:
    """The dashboard's core actionable numbers. For every record, find its
    single best same-category embedding candidate (vectorized numpy scan) and
    run it through Phase 4's ACTUAL, validated evaluate_pair() -- not a
    separate ad-hoc heuristic -- so "technical
    conflicts" and "pending review" mean exactly what the review queue and
    compatibility engine already mean elsewhere in this system.

    "Pending" excludes any record pair already covered by a review_decision --
    a decided pair isn't waiting on anyone.
    """
    if not _load_index():
        return {"available": False, "reason": "embedding index not built"}

    import app.embeddings as E

    docs = await db.records.find({}, {"category_predicted": 1, "attributes": 1}).to_list(length=None)
    id_to_doc = {str(d["_id"]): d for d in docs}

    decided_pairs = set()
    async for d in db.review_decisions.find({}, {"record_a_id": 1, "record_b_id": 1}):
        decided_pairs.add(frozenset({d["record_a_id"], d["record_b_id"]}))

    cat_rows = defaultdict(list)
    for i, rid in enumerate(E._ids):
        doc = id_to_doc.get(rid)
        if doc:
            cat_rows[doc.get("category_predicted")].append(i)

    counts = {"SAME": 0, "EQUIVALENT": 0, "CONFLICT": 0, "INSUFFICIENT_INFORMATION": 0}
    pending_counts = {"CONFLICT": 0, "INSUFFICIENT_INFORMATION": 0}
    conflicts_by_category: dict[str, int] = {}

    for cat, rows in cat_rows.items():
        if cat is None or len(rows) < 2:
            continue
        rows_arr = np.array(rows)
        block = E._embeddings[rows_arr]
        sim_matrix = block @ block.T
        np.fill_diagonal(sim_matrix, -1.0)
        best_within = np.argmax(sim_matrix, axis=1)
        best_sims = sim_matrix[np.arange(len(rows_arr)), best_within]

        for local_i, global_i in enumerate(rows_arr):
            if best_sims[local_i] < SIMILARITY_FLOOR:
                continue
            rid = E._ids[global_i]
            match_rid = E._ids[rows_arr[best_within[local_i]]]
            if rid == match_rid:
                continue
            doc_r, doc_m = id_to_doc[rid], id_to_doc[match_rid]
            result = evaluate_pair(
                doc_r.get("category_predicted"), doc_r.get("attributes") or {},
                doc_m.get("category_predicted"), doc_m.get("attributes") or {},
            )
            verdict = result["verdict"]
            counts[verdict] = counts.get(verdict, 0) + 1
            if verdict == "CONFLICT":
                conflicts_by_category[cat] = conflicts_by_category.get(cat, 0) + 1
            if verdict in pending_counts and frozenset({rid, match_rid}) not in decided_pairs:
                pending_counts[verdict] += 1

    return {
        "available": True,
        "by_verdict": counts,
        "pending_review": pending_counts["CONFLICT"] + pending_counts["INSUFFICIENT_INFORMATION"],
        "pending_by_verdict": pending_counts,
        "technical_conflicts": counts["CONFLICT"],
        "conflicts_by_category": conflicts_by_category,
        "method": "each record's single best same-category embedding match, evaluated with the same "
                  f"Phase 4 rule engine used everywhere else (similarity >= {SIMILARITY_FLOOR}) -- an "
                  "estimate bounded by that one-best-match scope, not an exhaustive pairwise scan.",
    }


async def get_data_quality_report(db) -> dict:
    """Real, directly-computed data-quality signals -- deliberately limited to
    what the pipeline actually tracks. Does NOT invent categories like
    "unrecognized abbreviation" or "invalid unit" that aren't independently
    tracked as distinct signals today (extraction failures already surface as
    missing_critical, so a separate fabricated count would just double up)."""
    total = await db.records.count_documents({})

    missing_attrs = await db.records.count_documents({"missing_critical.0": {"$exists": True}})
    unclassified = await db.records.count_documents({"category_predicted": None})
    empty_description = await db.records.count_documents(
        {"$or": [{"description": None}, {"description": ""}, {"description": {"$regex": "^\\s*$"}}]}
    )

    dup_pipeline = [
        {"$group": {"_id": {"cpse": "$cpse", "legacy_code": "$legacy_code"}, "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
        {"$group": {"_id": None, "groups": {"$sum": 1}, "records": {"$sum": "$count"}}},
    ]
    dup_result = await db.records.aggregate(dup_pipeline).to_list(length=1)
    dup_groups = dup_result[0]["groups"] if dup_result else 0
    dup_records = dup_result[0]["records"] if dup_result else 0

    missing_by_attr_pipeline = [
        {"$match": {"missing_critical.0": {"$exists": True}}},
        {"$unwind": "$missing_critical"},
        {"$group": {"_id": "$missing_critical", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    missing_by_attr = {
        d["_id"]: d["count"] async for d in db.records.aggregate(missing_by_attr_pipeline)
    }

    return {
        "total_records": total,
        "missing_critical_attributes": missing_attrs,
        "unclassified_category": unclassified,
        "empty_description": empty_description,
        "duplicate_legacy_code_groups": dup_groups,
        "duplicate_legacy_code_records": dup_records,
        "missing_attribute_breakdown": missing_by_attr,
        "note": "duplicate_legacy_code_* flags CPSEs whose OWN code re-used the same value for two "
                "different materials -- this is a source-data integrity issue to route for review, "
                "not something this system silently resolves or blocks on ingestion.",
    }
