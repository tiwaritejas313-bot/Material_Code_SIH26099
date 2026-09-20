import math
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.attributes import extract
from app.auth import CurrentUser, get_current_user, require_role
from app.db import get_database
from app.embeddings import index_status
from app.grouping import serialize_group
from app.ingestion import IngestionError, parse_upload
from app.matching import rank_candidates
from app.normalization import normalize

router = APIRouter(prefix="/records", tags=["records"])

MAX_UPLOAD_BYTES = 10 * 1_000_000  # 10MB -- pandas reads the whole file into memory; real
                                    # uploads are tens of rows, not a bulk-load-sized file


def _serialize(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    return doc


def _clean(value):
    """pandas can hand back a bare float('nan') instead of None depending on
    the column-creation path; json.dumps chokes on it, so scrub it explicitly
    rather than trust .where()/dropna() to have already done it."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


@router.get("")
async def list_records(
    cpse: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = Query(default=25, le=200),
    offset: int = Query(default=0, ge=0),
    _user: CurrentUser = Depends(get_current_user),
):
    db = get_database()
    query: dict = {}
    if cpse:
        query["cpse"] = cpse
    if category:
        # category_predicted, not category_true -- the latter is eval-only and
        # doesn't exist on uploaded (non-Samanvay) records, which would
        # otherwise make this filter silently exclude all of them.
        query["category_predicted"] = category
    if source:
        query["source"] = source

    total = await db.records.count_documents(query)
    cursor = db.records.find(query).skip(offset).limit(limit)
    items = [_serialize(doc) async for doc in cursor]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/stats")
async def record_stats(_user: CurrentUser = Depends(get_current_user)):
    db = get_database()
    total = await db.records.count_documents({})
    by_cpse = await db.records.aggregate(
        [{"$group": {"_id": "$cpse", "count": {"$sum": 1}}}]
    ).to_list(length=None)
    by_source = await db.records.aggregate(
        [{"$group": {"_id": "$source", "count": {"$sum": 1}}}]
    ).to_list(length=None)
    by_category = await db.records.aggregate(
        [{"$group": {"_id": "$category_predicted", "count": {"$sum": 1}}}]
    ).to_list(length=None)
    return {
        "total": total,
        "by_cpse": {d["_id"]: d["count"] for d in by_cpse},
        "by_source": {d["_id"]: d["count"] for d in by_source},
        "by_category": {d["_id"]: d["count"] for d in by_category},
    }


@router.get("/{record_id}")
async def get_record(record_id: str, _user: CurrentUser = Depends(get_current_user)):
    db = get_database()
    try:
        oid = ObjectId(record_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid record id")
    doc = await db.records.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Record not found")
    return _serialize(doc)


@router.get("/{record_id}/attributes")
async def get_record_attributes(record_id: str, _user: CurrentUser = Depends(get_current_user)):
    """Live re-extraction (Phase 2) -- useful for records ingested after the last backfill."""
    db = get_database()
    try:
        oid = ObjectId(record_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid record id")
    doc = await db.records.find_one({"_id": oid}, {"normalized_description": 1, "description": 1, "category_true": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Record not found")
    result = extract(doc.get("normalized_description") or "")
    result["record_id"] = record_id
    result["category_true"] = doc.get("category_true")  # evaluation-only; not fed back into the model
    return result


@router.post("/upload")
async def upload_records(
    file: UploadFile = File(...),
    source: Optional[str] = Form(None),
    user: CurrentUser = Depends(require_role("admin")),
):
    """Phase 1 ingestion: accept a CPSE material-master CSV/Excel export, and run
    every row through normalization + attribute extraction (Phases 1+2) immediately,
    so uploaded data is never in a half-processed state waiting on a backfill script."""
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content) / 1_000_000:.1f} MB); limit is {MAX_UPLOAD_BYTES / 1_000_000:.0f} MB.",
        )
    try:
        df = parse_upload(file.filename, content)
    except IngestionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if len(df) == 0:
        raise HTTPException(status_code=400, detail="No valid rows found (missing cpse/legacy_code/description).")

    db = get_database()
    last = await db.records.find_one(sort=[("record_id", -1)])
    next_record_id = (last["record_id"] + 1) if last and isinstance(last.get("record_id"), int) else 1

    docs = []
    for i, row in df.iterrows():
        normalized = normalize(row["description"])
        extraction = extract(normalized)
        docs.append({
            "record_id": next_record_id + i,
            "cpse": _clean(row["cpse"]),
            "plant": _clean(row.get("plant")),
            "legacy_code": _clean(row["legacy_code"]),
            "description": _clean(row["description"]),
            "uom": _clean(row.get("uom")),
            "source": source or file.filename,
            "normalized_description": normalized,
            "category_predicted": extraction["category_predicted"],
            "attributes": {k: _clean(v) for k, v in extraction["attributes"].items()},
            "missing_critical": extraction["missing_critical"],
        })

    result = await db.records.insert_many(docs)

    # Phase 7: unlike the one-off bulk seed-data loader scripts, a real
    # user-driven upload IS audited -- one entry per record, since real
    # uploads are small (tens of rows, not Samanvay's 46k). actor is the
    # AUTHENTICATED username, not a self-reported form field, so this is now
    # actually verifiable rather than trusting whatever string was typed in.
    actor = user.username
    audit_entries = [
        {
            "entity_type": "record", "entity_id": str(rid), "action": "record_ingested",
            "actor": actor, "previous_value": None,
            "new_value": {"cpse": d["cpse"], "legacy_code": d["legacy_code"], "source": d["source"]},
            "reason": f"uploaded via {file.filename}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for d, rid in zip(docs, result.inserted_ids)
    ]
    if audit_entries:
        await db.audit_log.insert_many(audit_entries)

    return {
        "filename": file.filename,
        "rows_inserted": len(result.inserted_ids),
        "source": source or file.filename,
        "sample": [_serialize({**d, "_id": i}) for d, i in list(zip(docs, result.inserted_ids))[:3]],
    }


@router.get("/embeddings/status")
async def embeddings_status(_user: CurrentUser = Depends(get_current_user)):
    return index_status()


@router.get("/{record_id}/candidates")
async def get_candidates(
    record_id: str,
    top_k: int = Query(default=10, le=50),
    pool_size: int = Query(default=300, le=2000),
    same_category_only: bool = True,
    _user: CurrentUser = Depends(get_current_user),
):
    """Phase 3: candidate retrieval. Two-stage -- embedding similarity picks a
    broad pool (pool_size), then Phase 2's already-extracted hard attributes
    re-rank that pool (ATTR_BOOST_WEIGHT), because pure embedding similarity
    alone measured recall@5 ~37% on this dataset (hex_bolt/stud_bolt are
    >13k near-identical templated records differing only in numeric attribute
    values a general sentence embedding barely separates) while the blended
    score measured recall@5 ~63% -- see app.embeddings docstring for the
    validation this is based on."""
    db = get_database()
    try:
        oid = ObjectId(record_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid record id")

    query_doc = await db.records.find_one(
        {"_id": oid}, {"normalized_description": 1, "category_predicted": 1, "attributes": 1}
    )
    if not query_doc:
        raise HTTPException(status_code=404, detail="Record not found")

    ranked = await rank_candidates(db, query_doc, top_k=top_k, pool_size=pool_size, same_category_only=same_category_only)
    return {
        "record_id": record_id,
        "category_predicted": query_doc.get("category_predicted"),
        "query_attributes": query_doc.get("attributes") or {},
        "candidates": ranked,
    }


@router.get("/{record_id}/group")
async def get_record_group(record_id: str, _user: CurrentUser = Depends(get_current_user)):
    """Phase 6 traceability: given one CPSE's record, find the Common Material
    Group (if any) it has been merged into, and every other original CPSE
    code mapped to that same group."""
    db = get_database()
    try:
        ObjectId(record_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid record id")

    group = await db.common_material_groups.find_one({"status": "active", "members.record_id": record_id})
    if not group:
        return {"record_id": record_id, "group": None}
    return {"record_id": record_id, "group": serialize_group(group)}
