from fastapi import APIRouter

from app.db import get_database

router = APIRouter()


@router.get("/health")
async def health():
    db = get_database()
    try:
        await db.command("ping")
        mongo_ok = True
    except Exception:
        mongo_ok = False
    return {"status": "ok", "mongodb_connected": mongo_ok}
