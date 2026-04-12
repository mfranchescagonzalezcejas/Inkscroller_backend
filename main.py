import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chapters import router as chapters_router
from app.api.health import router as health_router
from app.api.manga import router as manga_router
from app.api.users import router as users_router
from app.core.cache import SimpleCache
from app.core.config import settings
from app.core.database import init_db
from app.core.exceptions import register_exception_handlers
from app.core.firebase_auth import init_firebase_admin
from app.core.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Database (SQLite local / PostgreSQL Cloud Run) ───────────
    init_firebase_admin()
    app.state.db = await init_db()

    # ── Upstream HTTP clients ────────────────────────────────────
    app.state.mangadex_http = httpx.AsyncClient(
        base_url=settings.mangadex_base_url,
        timeout=httpx.Timeout(10.0),
    )
    app.state.jikan_http = httpx.AsyncClient(
        base_url=settings.jikan_base_url,
        timeout=httpx.Timeout(10.0),
    )
    app.state.cache = SimpleCache(ttl_seconds=settings.cache_ttl_seconds)

    yield

    await app.state.mangadex_http.aclose()
    await app.state.jikan_http.aclose()
    await app.state.db.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    logger.info(
        "Inkscroller API v%s starting (debug=%s)", settings.version, settings.debug
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(manga_router)
    app.include_router(chapters_router)
    app.include_router(users_router)

    return app


app = create_app()
