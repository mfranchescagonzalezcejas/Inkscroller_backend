"""In-memory sliding-window rate limiter for FastAPI/ASGI middleware.

No external dependencies — uses ``time.monotonic()`` and a dict of
(deque of timestamps) per key.  Auto-evicts stale entries on access.
"""

import os
import time
from collections import defaultdict, deque

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

# ── Default limits ──────────────────────────────────────────────────────────
# (window_seconds, max_requests)

PUBLIC_ENDPOINT_LIMIT: tuple[int, int] = (60, 30)  # 30 req/min
AUTH_ENDPOINT_LIMIT: tuple[int, int] = (60, 60)  # 60 req/min (more generous)
STRICT_LIMIT: tuple[int, int] = (60, 10)  # 10 req/min (CSP report, etc.)

# ── Trusted proxy detection ─────────────────────────────────────────────────
# When behind a reverse proxy that validates and strips external
# X-Forwarded-For (e.g. Railway, Cloudflare), set TRUSTED_PROXY=true
# so the rate limiter uses the original client IP, not the proxy IP.

_TRUSTED_PROXY = os.getenv("TRUSTED_PROXY", "").lower() in {"1", "true", "yes"}

# ── Route category helpers ──────────────────────────────────────────────────

_STRICT_PREFIXES = frozenset({"/csp-report"})
_AUTH_PREFIXES = frozenset({"/users"})


def _route_category(path: str) -> tuple[int, int]:
    """Return (window_seconds, max_requests) for the given path."""
    if any(path.startswith(p) for p in _STRICT_PREFIXES):
        return STRICT_LIMIT
    if any(path.startswith(p) for p in _AUTH_PREFIXES):
        return AUTH_ENDPOINT_LIMIT
    return PUBLIC_ENDPOINT_LIMIT


# ── In-memory store ─────────────────────────────────────────────────────────

_MAX_BUCKETS = 10_000


class _SlidingWindowStore:
    """Dict-of-deques backed sliding window rate counter.

    Each key is ``rl:<client-host>:<category>`` — at most 3 buckets per
    client (public, auth, strict), preventing path-churn attacks.

    Bounded to ``_MAX_BUCKETS`` distinct keys.  Thread-safe enough for
    GIL-protected ASGI because individual dict/deque operations are
    atomic under the GIL.
    """

    def __init__(self) -> None:
        """Initialise the store with an empty default-dict of deques."""
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def _evict_one(self) -> None:
        """Remove the bucket with the most recent timestamp (oldest active key)."""
        if not self._buckets:
            return
        oldest_key = min(self._buckets, key=lambda k: self._buckets[k][-1])
        del self._buckets[oldest_key]

    def reset(self) -> None:
        """Clear all rate-limit buckets (test isolation)."""
        self._buckets.clear()

    def _purge(self, key: str, window: int) -> None:
        """Remove timestamps older than *window* seconds."""
        cutoff = time.monotonic() - window
        bucket = self._buckets[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

    def is_limited(self, key: str, window: int, max_reqs: int) -> bool:
        """Check and record a request.  Returns ``True`` if it should be rejected."""
        self._purge(key, window)
        bucket = self._buckets[key]
        if len(bucket) >= max_reqs:
            return True
        bucket.append(time.monotonic())
        if len(self._buckets) > _MAX_BUCKETS:
            self._evict_one()
        return False


_store = _SlidingWindowStore()


def reset_for_tests() -> None:
    """Clear all rate-limit state.  Call in test ``setUp`` to isolate tests."""
    _store.reset()


# ── Client-IP resolution ────────────────────────────────────────────────────


def _client_ip_from_scope(scope: Scope) -> str:
    """Resolve the effective client IP from the ASGI scope.

    When ``TRUSTED_PROXY=true`` the ``X-Forwarded-For`` header is used
    (the proxy is responsible for stripping external headers).
    Otherwise the direct TCP peer address is used — unspoofable but
    behind a proxy it identifies the proxy, not the end user.
    """
    if _TRUSTED_PROXY:
        headers = dict(scope.get("headers", []))
        forwarded = headers.get(b"x-forwarded-for", b"").decode()
        return forwarded.split(",")[0].strip() or "unknown"
    client = scope.get("client")
    return client[0] if client else "unknown"


def _rate_key(scope: Scope, path: str) -> str:
    """Build a rate-limit key scoped by client and route category.

    Using the route category instead of the raw path prevents path-churn
    attacks (unlimited unique buckets per client).
    """
    cat = _route_category(path)
    return f"rl:{_client_ip_from_scope(scope)}:{cat[0]}s:{cat[1]}r"


# ── CORS helpers for 429 responses ──────────────────────────────────────────


def _cors_headers(scope: Scope) -> dict[str, str]:
    """Return CORS headers matching the request's Origin, if allowed."""
    from app.core.config import settings

    headers = dict(scope.get("headers", []))
    origin = headers.get(b"origin", b"").decode()
    if not origin:
        return {}
    allowed = settings.cors_origins
    if "*" in allowed or origin in allowed:
        return {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}
    return {}


# ── Callable dependency for FastAPI routes ──────────────────────────────────


async def rate_limit(
    request: Request,
    window: int | None = None,
    max_requests: int | None = None,
) -> None:
    """FastAPI dependency: reject with 429 if the client exceeds the limit.

    Usage::

        @router.get("/something")
        async def handler(_: None = Depends(rate_limit)):
            ...

    Per-route overrides::

        @router.get("/csp-report")
        async def csp(
            _: None = Depends(lambda r: rate_limit(r, window=60, max_requests=10)),
        ):
            ...
    """
    if window is None or max_requests is None:
        window, max_requests = _route_category(request.url.path)
    key = _rate_key(request.scope, request.url.path)
    if _store.is_limited(key, window, max_requests):
        raise _RateLimitError()


class _RateLimitError(Exception):
    """Raised (and caught by middleware) when the client exceeds the rate limit."""


# ── ASGI middleware ─────────────────────────────────────────────────────────


class RateLimitMiddleware:
    """ASGI middleware that applies sliding-window rate limits per client + route category.

    Keyed by route category (public/auth/strict) instead of raw path to
    prevent path-churn bucket exhaustion.  Includes CORS headers in 429
    responses so browsers can surface the rate-limit error to frontend code.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap the downstream ASGI application."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Inspect the request scope and reject with 429 if over the rate limit."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")
        window, max_reqs = _route_category(path)
        key = _rate_key(scope, path)

        if _store.is_limited(key, window, max_reqs):
            headers: dict[str, str] = {
                "content-type": "application/json",
                "retry-after": str(window),
            }
            headers.update(_cors_headers(scope))
            resp = JSONResponse(
                status_code=429,
                content={"error": "rate_limited", "detail": "Too many requests."},
                headers=headers,
            )
            await resp(scope, receive, send)
            return

        await self.app(scope, receive, send)


# ── Exception handler for the dependency-based calls ────────────────────────


async def handle_rate_limit_error(request: Request, exc: _RateLimitError) -> Response:
    """Return 429 when the rate-limit dependency fires."""
    window, _ = _route_category(request.url.path)
    return JSONResponse(
        status_code=429,
        content={"error": "rate_limited", "detail": "Too many requests."},
        headers={"Retry-After": str(window)},
    )
