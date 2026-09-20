from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.auth import CurrentUser, get_current_user
from app.db import get_database

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def list_audit_entries(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    _user: CurrentUser = Depends(get_current_user),
):
    """Phase 7. Filter by entity_type=common_material_group&entity_id=CNMC-000001
    for one group's full history, or entity_type=pair&entity_id=<a>:<b> for one
    pair's history, or no filters for the most recent activity across everything."""
    db = get_database()
    query: dict = {}
    if entity_type:
        query["entity_type"] = entity_type
    if entity_id:
        query["entity_id"] = entity_id

    cursor = db.audit_log.find(query).sort("timestamp", -1).limit(limit)
    items = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        items.append(doc)
    return {"items": items}
