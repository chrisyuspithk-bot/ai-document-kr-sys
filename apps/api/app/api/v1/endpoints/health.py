"""Liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.core.deps import DbSession

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(db: DbSession) -> dict:
    checks: dict[str, str] = {}
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    redis_client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
    finally:
        await redis_client.aclose()

    if any(value == "error" for value in checks.values()):
        raise HTTPException(status_code=503, detail={"status": "unavailable", "checks": checks})
    return {"status": "ready", "checks": checks}
