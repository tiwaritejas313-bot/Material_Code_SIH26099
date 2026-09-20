"""Shared candidate-ranking logic (Phase 3's hybrid embedding+attribute
ranker), used by both the /records/{id}/candidates endpoint and the Phase 5
review queue -- extracted here so the queue doesn't reimplement it."""
from bson import ObjectId

from app.attributes import HARD_ATTRIBUTES
from app.embeddings import find_candidate_pool

ATTR_BOOST_WEIGHT = 0.5  # validated on Samanvay's pairs_pos.csv: recall@5 37% -> 63%


async def rank_candidates(db, query_doc: dict, top_k: int = 10, pool_size: int = 300, same_category_only: bool = True) -> list[dict]:
    category = query_doc.get("category_predicted")
    category_filter = category if same_category_only else None
    query_text = query_doc.get("normalized_description") or ""
    exclude_id = str(query_doc["_id"])

    pool = find_candidate_pool(query_text, pool_size=pool_size, category_filter=category_filter, exclude_id=exclude_id)
    if not pool:
        return []

    pool_ids = [ObjectId(rid) for rid, _ in pool]
    cand_docs = {
        str(d["_id"]): d
        async for d in db.records.find(
            {"_id": {"$in": pool_ids}},
            {"cpse": 1, "legacy_code": 1, "description": 1, "category_predicted": 1, "attributes": 1},
        )
    }

    query_attrs = query_doc.get("attributes") or {}
    hard = HARD_ATTRIBUTES.get(category, [])

    ranked = []
    for rid, sim in pool:
        cand = cand_docs.get(rid)
        if not cand:
            continue
        cand_attrs = cand.get("attributes") or {}
        if hard:
            agree = sum(1 for h in hard if query_attrs.get(h) is not None and query_attrs.get(h) == cand_attrs.get(h))
            attr_agreement = agree / len(hard)
        else:
            attr_agreement = 0.0
        score = sim + ATTR_BOOST_WEIGHT * attr_agreement
        ranked.append({
            "record_id": rid,
            "cpse": cand.get("cpse"),
            "legacy_code": cand.get("legacy_code"),
            "description": cand.get("description"),
            "category_predicted": cand.get("category_predicted"),
            "embedding_similarity": round(sim, 4),
            "attribute_agreement": round(attr_agreement, 4),
            "score": round(score, 4),
        })

    ranked.sort(key=lambda r: -r["score"])
    return ranked[:top_k]
