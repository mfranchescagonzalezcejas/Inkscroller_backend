"""Health-check probes (liveness + readiness) for the application."""

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.core.config import settings
from app.core.db_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])


@router.get("/ping")
def ping() -> dict[str, bool]:
    """Liveness probe — returns ``{"ok": true}`` if the application is running."""
    return {"ok": True}


@router.get("/ready", response_model=None)
async def ready(request: Request) -> Response:
    """Readiness probe — validates DB connectivity with a short timeout."""
    db: DatabaseAdapter = request.app.state.db

    try:
        result = await asyncio.wait_for(
            db.fetchone("SELECT 1 AS ok"),
            timeout=settings.readyz_timeout_seconds,
        )
        if result and result.get("ok") == 1:
            return JSONResponse(
                status_code=200,
                content={"ready": True, "database": "ok"},
            )
        return JSONResponse(
            status_code=503,
            content={"ready": False, "database": "unexpected_response"},
        )
    except TimeoutError:
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
