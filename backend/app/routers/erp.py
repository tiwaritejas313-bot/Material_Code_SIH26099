"""
Phase 9: SAP/ERP integration -- honestly scoped as a prototype data contract,
not a live SAP connection (see the earlier risk analysis: "a web application
importing CSV files is not the same as integrating with a live SAP system").

INBOUND direction (ERP -> platform): handled by the existing, already-tested
POST /records/upload -- app.ingestion now also recognizes SAP's own MARA/MAKT/
MARC field names (MATNR/MAKTX/WERKS/BUKRS/MEINS), so a genuine SAP flat-file
export ingests through the identical pipeline as any other CPSE file, rather
than a second parallel import path.

OUTBOUND direction (platform -> ERP): this router. Exports approved Common
Material Group mappings shaped like a SAP material-master extract, with the
harmonization-specific fields given a "ZZ" prefix -- the real SAP convention
for a customer's own custom fields, not a standard MARA column pretending to
be one.
"""
import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.auth import CurrentUser, get_current_user
from app.db import get_database

router = APIRouter(prefix="/erp", tags=["erp"])

SAP_FIELDS = ["BUKRS", "MATNR", "MAKTX", "MATKL", "ZZCNMC_CODE", "ZZCANONICAL_DESC", "ZZMAPPING_STATUS"]


async def _build_export_rows(db, status: str | None) -> list[dict]:
    query = {"status": status} if status else {}
    rows = []
    async for group in db.common_material_groups.find(query):
        record_ids = [m["record_id"] for m in group["members"]]
        from bson import ObjectId
        cursor = db.records.find(
            {"_id": {"$in": [ObjectId(r) for r in record_ids]}}, {"description": 1}
        )
        desc_by_id = {str(d["_id"]): d.get("description") async for d in cursor}
        for m in group["members"]:
            rows.append({
                "BUKRS": m["cpse"],
                "MATNR": m["legacy_code"],
                "MAKTX": desc_by_id.get(m["record_id"], ""),
                "MATKL": group["category"],
                "ZZCNMC_CODE": group["common_code"],
                "ZZCANONICAL_DESC": group.get("canonical_description") or "",
                "ZZMAPPING_STATUS": group["status"],
            })
    return rows


@router.get("/export")
async def export_mappings(
    format: str = Query(default="csv", pattern="^(csv|json)$"),
    status: str = "active",
    _user: CurrentUser = Depends(get_current_user),
):
    """Prototype SAP-style material-master extract of approved harmonization
    mappings -- NOT a certified IDoc/BAPI format, and not connected to a live
    SAP system. Demonstrates the data contract per the earlier documentation's
    explicit guidance to label this "integration-ready," not production."""
    db = get_database()
    rows = await _build_export_rows(db, status if status != "all" else None)

    if format == "json":
        return {"fields": SAP_FIELDS, "rows": rows, "note": "Prototype SAP-style extract, not a live SAP/IDoc feed."}

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=SAP_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cnmc_mapping_export.csv"},
    )
