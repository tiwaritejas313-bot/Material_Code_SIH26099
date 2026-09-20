from datetime import datetime, timezone
from typing import Literal, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, model_validator

from app.audit import log_action
from app.auth import CurrentUser, get_current_user, require_role
from app.compatibility import evaluate_pair
from app.db import get_database
from app.embeddings import similarity_between
from app.grouping import handle_accept, serialize_group
from app.matching import rank_candidates

router = APIRouter(prefix="/pairs", tags=["pairs"])


class EvaluateRequest(BaseModel):
    record_a_id: str
    record_b_id: str

    @model_validator(mode="after")
    def not_self_paired(self):
        if self.record_a_id == self.record_b_id:
            raise ValueError("record_a_id and record_b_id must be different records")
        return self


class DecisionRequest(BaseModel):
    record_a_id: str
    record_b_id: str
    # No "reviewer" field -- it used to be free text anyone could type,
    # which made the audit trail's actor unverifiable. The reviewer identity
    # now comes from the authenticated JWT (see submit_decision below).
    action: Literal["accept", "reject", "escalate"]
    reason: Optional[str] = None

    @model_validator(mode="after")
    def not_self_paired(self):
        if self.record_a_id == self.record_b_id:
            raise ValueError("record_a_id and record_b_id must be different records")
        return self

    @model_validator(mode="after")
    def reason_required_for_reject_or_escalate(self):
        # Explicit governance requirement: a reviewer overriding or deferring
        # an AI recommendation must say why -- "reject" with no reason gives
        # the audit trail nothing useful to show later.
        if self.action in ("reject", "escalate") and (not self.reason or not self.reason.strip()):
            raise ValueError(f"a reason is required when action is '{self.action}'")
        return self


def _record_summary(doc: dict) -> dict:
    return {
        "record_id": str(doc["_id"]),
        "cpse": doc.get("cpse"),
        "legacy_code": doc.get("legacy_code"),
        "description": doc.get("description"),
        "normalized_description": doc.get("normalized_description"),
        "category_predicted": doc.get("category_predicted"),
        "attributes": doc.get("attributes") or {},
    }


@router.post("/evaluate")
async def evaluate(req: EvaluateRequest, _user: CurrentUser = Depends(get_current_user)):
    """Phase 4: the safety gate. Verdict (SAME/EQUIVALENT/CONFLICT/
    INSUFFICIENT_INFORMATION) is decided by deterministic attribute
    comparison -- see app.compatibility for why, and app.compatibility's
    validation against pairs_hardneg.csv (zero false merges) and our own
    custom_gap_test_set (23/23 correct) for the evidence this is safe."""
    db = get_database()
    try:
        oid_a, oid_b = ObjectId(req.record_a_id), ObjectId(req.record_b_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid record id")

    doc_a = await db.records.find_one({"_id": oid_a})
    doc_b = await db.records.find_one({"_id": oid_b})
    if not doc_a or not doc_b:
        raise HTTPException(status_code=404, detail="One or both records not found")

    sim = similarity_between(
        req.record_a_id, doc_a.get("normalized_description") or "",
        req.record_b_id, doc_b.get("normalized_description") or "",
    )

    result = evaluate_pair(
        doc_a.get("category_predicted"), doc_a.get("attributes") or {},
        doc_b.get("category_predicted"), doc_b.get("attributes") or {},
        embedding_similarity=sim,
    )

    return {
        "record_a": _record_summary(doc_a),
        "record_b": _record_summary(doc_b),
        **result,
    }


@router.post("/decision")
async def submit_decision(req: DecisionRequest, user: CurrentUser = Depends(require_role("admin"))):
    """Phase 5: persist a reviewer's decision. The system_verdict is
    RE-COMPUTED here rather than trusted from the client, so a decision
    record always reflects what the engine actually said, not whatever the
    frontend happened to send. The reviewer identity is the authenticated
    user, not a request field -- see DecisionRequest's comment."""
    db = get_database()
    try:
        oid_a, oid_b = ObjectId(req.record_a_id), ObjectId(req.record_b_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid record id")

    doc_a = await db.records.find_one({"_id": oid_a})
    doc_b = await db.records.find_one({"_id": oid_b})
    if not doc_a or not doc_b:
        raise HTTPException(status_code=404, detail="One or both records not found")

    result = evaluate_pair(
        doc_a.get("category_predicted"), doc_a.get("attributes") or {},
        doc_b.get("category_predicted"), doc_b.get("attributes") or {},
    )

    decision = {
        "record_a_id": req.record_a_id,
        "record_b_id": req.record_b_id,
        "system_verdict": result["verdict"],
        "reviewer": user.username,
        "action": req.action,
        "reason": req.reason,
        "decided_at": datetime.now(timezone.utc).isoformat(),
    }
    insert_result = await db.review_decisions.insert_one(decision)
    decision["_id"] = str(insert_result.inserted_id)

    # Phase 7: the review decision itself is always an audited event --
    # "AI suggested X -> reviewer did Y -> reason: Z", exactly the governance
    # trail the PS asks for.
    pair_id = f"{req.record_a_id}:{req.record_b_id}"
    await log_action(
        db, entity_type="pair", entity_id=pair_id, action=f"reviewer_{req.action}",
        actor=user.username, previous_value=result["verdict"], new_value=req.action, reason=req.reason,
    )

    group = None
    if req.action == "accept":
        # Phase 6: an accepted pair grows (or creates, or merges) a Common
        # Material Group. Note this proceeds even if system_verdict was
        # CONFLICT/INSUFFICIENT_INFORMATION -- the reviewer is the final
        # authority in this human-in-the-loop design, and may have
        # out-of-band knowledge the rule engine doesn't (e.g. confirming two
        # plants really do use interchangeable connection types on site).
        group_doc, event = await handle_accept(db, doc_a, doc_b)
        group = serialize_group(group_doc)

        if event["type"] == "created":
            await log_action(
                db, entity_type="common_material_group", entity_id=event["common_code"],
                action="group_created", actor=user.username, previous_value=None,
                new_value=event["common_code"], reason=f"created from accepted pair {pair_id}",
            )
        elif event["type"] == "extended":
            await log_action(
                db, entity_type="common_material_group", entity_id=event["common_code"],
                action="group_extended", actor=user.username,
                previous_value=len(group["members"]) - 1, new_value=len(group["members"]),
                reason=f"member added via accepted pair {pair_id}",
            )
        elif event["type"] == "merged":
            await log_action(
                db, entity_type="common_material_group", entity_id=event["common_code"],
                action="group_merged", actor=user.username,
                previous_value=event["superseded_code"], new_value=event["common_code"],
                reason=f"{event['superseded_code']} merged into {event['common_code']} via accepted pair {pair_id}",
            )

    return {**decision, "group": group}


@router.get("/decisions")
async def list_decisions(limit: int = Query(default=50, le=500), _user: CurrentUser = Depends(get_current_user)):
    db = get_database()
    cursor = db.review_decisions.find({}).sort("decided_at", -1).limit(limit)
    items = []
    async for d in cursor:
        d["_id"] = str(d["_id"])
        items.append(d)
    return {"items": items}


_VERDICT_PRIORITY = {"CONFLICT": 0, "INSUFFICIENT_INFORMATION": 1, "EQUIVALENT": 2, "SAME": 3}


@router.get("/queue")
async def get_review_queue(
    limit: int = Query(default=20, le=100),
    category: Optional[str] = None,
    source: Optional[str] = None,
    scan_limit: int = Query(default=300, le=2000),
    _user: CurrentUser = Depends(get_current_user),
):
    """Phase 5: a review queue generated on demand -- for each not-yet-decided
    record, find its single best candidate (Phase 3) and evaluate it (Phase 4),
    then surface CONFLICT / INSUFFICIENT_INFORMATION pairs first since those are
    exactly the cases that need a human judgment call, per the PS's own
    "human validation and approval workflow" requirement.

    Without a source filter, this scans records in roughly insertion order --
    with tens of thousands of pre-loaded benchmark records inserted long
    before any real upload, a freshly-uploaded file's own rows would never be
    reached within a sane scan_limit. source lets you point the scan at just
    your own upload."""
    db = get_database()

    decided_pairs = set()
    async for d in db.review_decisions.find({}, {"record_a_id": 1, "record_b_id": 1}):
        decided_pairs.add(frozenset({d["record_a_id"], d["record_b_id"]}))

    query: dict = {}
    if category:
        query["category_predicted"] = category
    if source:
        query["source"] = source

    queue = []
    seen_pairs = set()
    cursor = db.records.find(
        query, {"cpse": 1, "legacy_code": 1, "description": 1, "normalized_description": 1,
                "category_predicted": 1, "attributes": 1}
    ).limit(scan_limit)

    async for doc in cursor:
        rid = str(doc["_id"])
        candidates = await rank_candidates(db, doc, top_k=1, pool_size=50, same_category_only=True)
        if not candidates:
            continue
        best = candidates[0]
        pair_key = frozenset({rid, best["record_id"]})
        if pair_key in decided_pairs or pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        cand_full = await db.records.find_one({"_id": ObjectId(best["record_id"])})
        result = evaluate_pair(
            doc.get("category_predicted"), doc.get("attributes") or {},
            cand_full.get("category_predicted"), cand_full.get("attributes") or {},
            embedding_similarity=best["embedding_similarity"],
        )
        queue.append({
            "record_a": _record_summary(doc),
            "record_b": _record_summary(cand_full),
            **result,
        })
        if len(queue) >= limit * 3:  # gather a bit extra so sorting by priority is meaningful
            break

    queue.sort(key=lambda q: _VERDICT_PRIORITY.get(q["verdict"], 4))
    return {"queue": queue[:limit]}
