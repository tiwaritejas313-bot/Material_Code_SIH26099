import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.logging_config import logger
from app.routers import audit, auth, dashboard, erp, groups, health, pairs, records

app = FastAPI(title="SIH26099 Material Harmonization API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # the actual verbs this API uses -- no PUT/DELETE/PATCH exist
    allow_headers=["Authorization", "Content-Type"],  # the two headers requests actually send
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - start) * 1000
    logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms:.0f}ms)")
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # HTTPException and Pydantic's RequestValidationError are already handled
    # by FastAPI's own defaults with proper status codes -- this only catches
    # genuinely unexpected failures (a bug, a DB timeout, etc.), logs the full
    # traceback server-side, and returns a generic message so internals never
    # leak into a client-facing error response.
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(records.router)
app.include_router(pairs.router)
app.include_router(groups.router)
app.include_router(audit.router)
app.include_router(dashboard.router)
app.include_router(erp.router)
