from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from app.api.health import router as health_router
from app.api.manga import router as manga_router
from app.api.chapters import router as chapters_router
from app.core.cache import SimpleCache
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
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


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.include_router(health_router)
    app.include_router(manga_router)
    app.include_router(chapters_router)

    return app


app = create_app()
