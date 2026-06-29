import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.db_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/ping")
def ping():
    return {"ok": True}


@router.get("/ready")
async def ready(request: Request):
    """Readiness probe — validates DB connectivity with a short timeout."""
    db: DatabaseAdapter = request.app.state.db

    try:
        result = await asyncio.wait_for(
            db.fetchone("SELECT 1 AS ok"),
            timeout=settings.readyz_timeout_seconds,
        )
        if result and result.get("ok") == 1:
            return {"ready": True, "database": "ok"}
        return JSONResponse(
            status_code=503,
            content={"ready": False, "database": "unexpected_response"},
        )
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=503,
            content={"ready": False, "database": "timeout"},
        )
    except Exception as exc:
        logger.error("Readiness check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"ready": False, "database": "error"},
        )
