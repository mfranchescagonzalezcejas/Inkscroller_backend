"""In-memory sliding-window rate limiter for FastAPI/ASGI middleware.

No external dependencies — uses ``time.monotonic()`` and a dict of
(deque of timestamps) per key.  Auto-evicts stale entries on access.
"""

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


class _SlidingWindowStore:
    """Dict-of-deques backed sliding window rate counter.

    Thread-safe enough for GIL-protected ASGI because individual dict/
    deque operations are atomic under the GIL and we never iterate while
    mutating (each request touches exactly one key at a time).
    """

    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

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
        return False


_store = _SlidingWindowStore()


def reset_for_tests() -> None:
    """Clear all rate-limit state.  Call in test ``setUp`` to isolate tests."""
    _store.reset()


# ── Callable dependency for FastAPI routes ──────────────────────────────────


def _client_key(request: Request) -> str:
    """Build a rate-limit key from the client IP."""
    forwarded = request.headers.get("x-forwarded-for", "")
    client = (
        forwarded.split(",")[0].strip() or request.client.host
        if request.client
        else "unknown"
    )
    return f"rl:{client}"


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
    key = _client_key(request) + request.url.path
    if _store.is_limited(key, window, max_requests):
        raise _RateLimitError()


class _RateLimitError(Exception):
    """Raised (and caught by middleware) when the client exceeds the rate limit."""


# ── ASGI middleware ─────────────────────────────────────────────────────────


class RateLimitMiddleware:
    """ASGI middleware that applies sliding-window rate limits per IP + path.

    Falls back to the per-route defaults from PUBLIC_ENDPOINT_LIMIT,
    AUTH_ENDPOINT_LIMIT, and STRICT_LIMIT.  Endpoints that already use
    the ``rate_limit`` dependency are still covered by the middleware
    catch-all — the dependency is just finer-grained control.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")
        window, max_reqs = _route_category(path)

        # Build client key
        headers = dict(scope.get("headers", {}))
        forwarded = headers.get(b"x-forwarded-for", b"").decode()
        client = forwarded.split(",")[0].strip() or (
            scope.get("client", ("unknown", 0))[0] or "unknown"
        )
        key = f"rl:{client}:{path}"

        if _store.is_limited(key, window, max_reqs):
            resp = JSONResponse(
                status_code=429,
                content={"error": "rate_limited", "detail": "Too many requests."},
                headers={
                    "content-type": "application/json",
                    "retry-after": str(window),
                },
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
