from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import CurrentUser, get_current_user
from app.db import get_database
from app.grouping import serialize_group

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("")
async def list_groups(
    status: str = "active",
    category: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    _user: CurrentUser = Depends(get_current_user),
):
    db = get_database()
    query: dict = {}
    if status:
        query["status"] = status
    if category:
        query["category"] = category

    total = await db.common_material_groups.count_documents(query)
    cursor = db.common_material_groups.find(query).sort("common_code", 1).skip(offset).limit(limit)
    items = [serialize_group(g) async for g in cursor]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/{common_code}")
async def get_group(common_code: str, _user: CurrentUser = Depends(get_current_user)):
    db = get_database()
    group = await db.common_material_groups.find_one({"common_code": common_code})
    if not group:
        raise HTTPException(status_code=404, detail="Common material group not found")
    return serialize_group(group)


@router.get("/search/lookup")
async def legacy_mapping_search(code: str = Query(min_length=1), _user: CurrentUser = Depends(get_current_user)):
    """Legacy mapping search, either direction, from one input box:
    - a Common Material Code (CNMC-...) -> every original CPSE code mapped to it
    - an original CPSE legacy_code -> which common code (if any) it maps to,
      plus every sibling code in the same group
    Matches case-insensitively since legacy codes come from many CPSEs' own
    (inconsistent) formatting conventions."""
    db = get_database()
    code = code.strip()

    group = await db.common_material_groups.find_one({"common_code": {"$regex": f"^{code}$", "$options": "i"}})
    if group:
        return {"query": code, "match_type": "common_code", "group": serialize_group(group)}

    record = await db.records.find_one({"legacy_code": {"$regex": f"^{code}$", "$options": "i"}})
    if not record:
        raise HTTPException(status_code=404, detail=f"No record or common code found matching '{code}'")

    result = {
        "query": code,
        "match_type": "legacy_code",
        "record": {
            "record_id": str(record["_id"]),
            "cpse": record.get("cpse"),
            "legacy_code": record.get("legacy_code"),
            "description": record.get("description"),
            "category_predicted": record.get("category_predicted"),
        },
        "common_code": record.get("common_code"),
        "group": None,
    }
    if record.get("common_code"):
        group = await db.common_material_groups.find_one({"common_code": record["common_code"]})
        if group:
            result["group"] = serialize_group(group)
    return result
