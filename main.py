import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncContextManager, Callable

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.chapters import router as chapters_router
from app.api.health import router as health_router
from app.api.manga import router as manga_router
from app.api.security import router as security_router
from app.api.users import router as users_router
from app.core.cache import SimpleCache
from app.core.config import settings
from app.core.database import init_db
from app.core.exceptions import register_exception_handlers
from app.core.firebase_auth import init_firebase_admin
from app.core.logging import setup_logging
from app.core.security_headers import get_security_headers
from app.services.user_service import UserService

setup_logging()
logger = logging.getLogger(__name__)


def build_lifespan(
    db_path: str | None = None,
) -> Callable[[FastAPI], AsyncContextManager[None]]:
    @asynccontextmanager
    async def app_lifespan(app: FastAPI):
        db = None
        mangadex_http = None
        mangadex_worker_http = None
        jikan_http = None

        try:
            # ── Database (SQLite local / PostgreSQL) ─────────────────────
            init_firebase_admin()
            db = app.state.db = await init_db(db_path)

            # ── Reconcile pending Firebase deletions ─────────────────────
            user_svc = UserService(db)
            await user_svc.process_all_pending_deletions()

            # ── Upstream HTTP clients ────────────────────────────────────
            user_agent = "InkScroller/1.0"
            if settings.mangadex_contact:
                user_agent += f" ({settings.mangadex_contact})"
            mangadex_http = app.state.mangadex_http = httpx.AsyncClient(
                base_url=settings.mangadex_base_url,
                timeout=httpx.Timeout(10.0),
                headers={"User-Agent": user_agent},
            )
            jikan_http = app.state.jikan_http = httpx.AsyncClient(
                base_url=settings.jikan_base_url,
                timeout=httpx.Timeout(10.0),
            )
            if settings.mangadex_worker_url:
                mangadex_worker_http = app.state.mangadex_worker_http = (
                    httpx.AsyncClient(
                        base_url=settings.mangadex_worker_url,
                        timeout=httpx.Timeout(10.0),
                    )
                )
            app.state.cache = SimpleCache(ttl_seconds=settings.cache_ttl_seconds)

            yield
        finally:
            if mangadex_http is not None:
                await mangadex_http.aclose()
            if mangadex_worker_http is not None:
                await mangadex_worker_http.aclose()
            if jikan_http is not None:
                await jikan_http.aclose()
            if db is not None:
                await db.close()

    return app_lifespan


lifespan = build_lifespan()


class RequestBodyLimitMiddleware:
    """Pure-ASGI middleware that rejects request bodies larger than ``max_bytes``.

    Checks ``Content-Length`` header before reading any body data to avoid
    buffering oversized payloads. Also counts received bytes for requests
    without a usable content-length (e.g. chunked transfer).

    Security headers are NOT added here — the outer ``SecurityHeadersMiddleware``
    handles all responses (normal, 413, 504, 500).
    """

    def __init__(self, app: ASGIApp, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # ── Early rejection via Content-Length ────────────────────────
        for key, value in scope.get("headers", []):
            if key == b"content-length":
                try:
                    declared = int(value)
                    if declared > self.max_bytes:
                        await _error_413(scope, receive, send)
                        return
                except (ValueError, TypeError):
                    pass  # Malformed header — fall through to chunk counting
                break

        total = 0
        messages: list[dict] = []
        more_body = True

        while more_body:
            message = await receive()
            messages.append(message)

            if message["type"] != "http.request":
                more_body = False
                continue

            total += len(message.get("body", b""))
            if total > self.max_bytes:
                await _error_413(scope, receive, send)
                return

            more_body = message.get("more_body", False)

        async def wrapped_receive() -> dict:
            if messages:
                return messages.pop(0)
            return await receive()

        await self.app(scope, wrapped_receive, send)


class SecurityHeadersMiddleware:
    """ASGI middleware that adds security headers to every HTTP response."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = get_security_headers(settings.is_production_like())
        header_items: list[tuple[bytes, bytes]] = [
            (k.lower().encode(), v.encode()) for k, v in headers.items()
        ]

        async def _send(message: dict) -> None:
            if message["type"] == "http.response.start":
                existing = message.get("headers", [])
                existing_keys = {k.lower() for k, _ in existing}
                missing = [(k, v) for k, v in header_items if k not in existing_keys]
                if missing:
                    message["headers"] = existing + missing
            await send(message)

        await self.app(scope, receive, _send)


class TimeoutMiddleware:
    """ASGI middleware that cancels downstream and returns 504 on timeout.

    Reads ``settings.request_timeout_seconds`` at request time so tests
    that patch settings after app creation work correctly.
    Security headers come from the outer ``SecurityHeadersMiddleware``.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        try:
            await asyncio.wait_for(
                self.app(scope, receive, send),
                timeout=settings.request_timeout_seconds,
            )
        except asyncio.TimeoutError:
            await _error_504(scope, receive, send)


def create_app(
    lifespan_context: Callable[[FastAPI], AsyncContextManager[None]] = lifespan,
) -> FastAPI:
    settings.validate_cors_configuration()

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        debug=settings.debug,
        lifespan=lifespan_context,
    )

    logger.info(
        "Inkscroller API v%s starting (debug=%s)", settings.version, settings.debug
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(
        RequestBodyLimitMiddleware,
        max_bytes=settings.max_request_body_mb * 1024 * 1024,
    )
    app.add_middleware(TimeoutMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(security_router)
    app.include_router(manga_router)
    app.include_router(chapters_router)
    app.include_router(users_router)

    return app


app = create_app()


# ── Helpers for middleware error responses ──────────────────────────────


def _find_origin(scope: Scope) -> str | None:
    """Return the ``Origin`` header value from the request scope, if any."""
    for key, value in scope.get("headers", []):
        if key == b"origin":
            return value.decode("ascii", errors="ignore") or None
    return None


def _cors_headers(origin: str | None) -> dict[str, str]:
    """Build CORS headers for error responses that bypass CORSMiddleware."""
    if not origin:
        return {}
    allowed = settings.cors_origins
    if "*" in allowed or origin in allowed:
        return {
            "Access-Control-Allow-Origin": origin,
            "Vary": "Origin",
        }
    if settings.is_production_like() and settings.cors_allow_credentials:
        # Production with credentials — only explicit origins
        if origin in allowed:
            return {
                "Access-Control-Allow-Origin": origin,
                "Vary": "Origin",
                "Access-Control-Allow-Credentials": "true",
            }
        return {}
    if not settings.is_production_like():
        return {
            "Access-Control-Allow-Origin": origin,
            "Vary": "Origin",
        }
    return {}


async def _error_413(scope: Scope, receive: Receive, send: Send) -> None:
    """Send a 413 response with security + CORS headers."""
    origin = _find_origin(scope)
    headers = get_security_headers(settings.is_production_like())
    headers.update(_cors_headers(origin))
    await Response(
        content=json.dumps({"detail": "Request body too large"}),
        status_code=413,
        media_type="application/json",
        headers=headers,
    )(scope, receive, send)


async def _error_504(scope: Scope, receive: Receive, send: Send) -> None:
    """Send a 504 response with security + CORS headers."""
    origin = _find_origin(scope)
    headers = get_security_headers(settings.is_production_like())
    headers.update(_cors_headers(origin))
    await Response(
        content=json.dumps({"detail": "Gateway Timeout"}),
        status_code=504,
        media_type="application/json",
        headers=headers,
    )(scope, receive, send)
