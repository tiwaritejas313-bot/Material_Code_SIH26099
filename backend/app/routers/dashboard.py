from fastapi import APIRouter, Depends

from app.analytics import get_data_quality_report, get_match_status_summary
from app.auth import CurrentUser, get_current_user
from app.db import get_database

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


async def _count_by(db, collection: str, field: str) -> dict:
    pipeline = [{"$group": {"_id": f"${field}", "count": {"$sum": 1}}}]
    rows = await db[collection].aggregate(pipeline).to_list(length=None)
    return {r["_id"]: r["count"] for r in rows}


@router.get("/summary")
async def dashboard_summary(_user: CurrentUser = Depends(get_current_user)):
    """Production dashboard, organized around three questions a material
    reviewer actually asks -- not one card per statistic. Every count is a
    live query; nothing is cached or precomputed."""
    db = get_database()

    total_records = await db.records.count_documents({})
    mapped_records = await db.records.count_documents({"common_code": {"$exists": True, "$ne": None}})
    active_groups = await db.common_material_groups.count_documents({"status": "active"})
    decision_counts = await _count_by(db, "review_decisions", "action")

    match_status = await get_match_status_summary(db)
    data_quality = await get_data_quality_report(db)

    return {
        # "What needs my attention?"
        "action_required": {
            "pending_review": match_status.get("pending_review", 0),
            "pending_conflicts": match_status.get("pending_by_verdict", {}).get("CONFLICT", 0),
            "pending_insufficient_information": match_status.get("pending_by_verdict", {}).get("INSUFFICIENT_INFORMATION", 0),
        },
        # "What has been processed?"
        "processed": {
            "total_records": total_records,
            "approved_material_groups": active_groups,
            "mapped_to_a_common_code": mapped_records,
            "decisions_accepted": decision_counts.get("accept", 0),
            "decisions_rejected": decision_counts.get("reject", 0),
            "decisions_escalated": decision_counts.get("escalate", 0),
        },
        # "Where are the problems?"
        "data_quality": data_quality,
        "technical_conflicts_by_category": match_status.get("conflicts_by_category", {}),
        "match_status_method": match_status.get("method"),
    }


@router.get("/breakdown")
async def dashboard_breakdown(_user: CurrentUser = Depends(get_current_user)):
    """Secondary context (not headline numbers) -- records by CPSE and
    category, for when a reviewer wants to drill into where the data comes
    from, not what needs a decision right now."""
    db = get_database()
    by_cpse = await _count_by(db, "records", "cpse")
    by_category = await _count_by(db, "records", "category_predicted")
    return {"by_cpse": by_cpse, "by_category": by_category}
