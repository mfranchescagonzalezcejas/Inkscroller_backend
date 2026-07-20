"""HTTP client for the MangaDex v5 REST API with per-method retry support."""

import asyncio
from typing import Any, cast

import httpx
from app.core.resilience import with_retry

# Default slot spacing: 0.25 s → maximum 4 requests per second,
# safely under MangaDex's documented ~5 req/s per-IP limit.
_REQUEST_INTERVAL_SECONDS = 0.25
# Cap for the Retry-After cooldown so a single 429 never silences
# the client for longer than one minute.
_MAX_RETRY_AFTER_SECONDS = 60.0
# HTTP status codes the MangaDex client will retry.  429 is excluded
# because MangaDex explicitly escalates repeated 429 traffic to a
# temporary IP ban (403) and eventual disconnection.
_RETRYABLE_STATUS_CODES = frozenset({500, 502, 503, 504})


class _MangaDexRateLimiter:
    """Async rate limiter that reserves evenly spaced request slots shared by all MangaDex clients.

    Uses ``asyncio.Lock`` to guard the scheduling clock so concurrent
    callers never overlap.  A 429 ``Retry-After``
    (see :meth:`cooldown`) temporarily pauses **all** future requests
    through this limiter, regardless of which client triggered it.
    """

    def __init__(self, interval_seconds: float = _REQUEST_INTERVAL_SECONDS) -> None:
        """Initialise the rate limiter with a fixed interval between requests.

        Args:
            interval_seconds: Minimum gap between consecutive outbound
                requests (default: 0.25 s → 4 req/s).
        """
        self._interval_seconds = interval_seconds
        self._lock = asyncio.Lock()
        self._next_request_at = 0.0
        self._cooldown_until = 0.0

    async def wait(self) -> None:
        """Wait for this request's slot without holding the scheduling lock."""
        loop = asyncio.get_running_loop()
        async with self._lock:
            now = loop.time()
            scheduled_at = max(now, self._next_request_at)
            self._next_request_at = scheduled_at + self._interval_seconds

        while True:
            delay = scheduled_at - loop.time()
            if delay > 0:
                await asyncio.sleep(delay)
            async with self._lock:
                if scheduled_at >= self._cooldown_until:
                    return
                scheduled_at = max(loop.time(), self._next_request_at)
                self._next_request_at = scheduled_at + self._interval_seconds

    async def cooldown(self, seconds: float) -> None:
        """Delay all later requests after an upstream throttle response."""
        async with self._lock:
            self._cooldown_until = max(
                self._cooldown_until, asyncio.get_running_loop().time() + seconds
            )
            self._next_request_at = max(self._next_request_at, self._cooldown_until)


# Singleton rate limiter — the primary client and the worker (union-scan)
# client share the same instance so their combined traffic honours the
# 4 req/s ceiling.
_shared_rate_limiter = _MangaDexRateLimiter()


class MangaDexClient:
    """HTTP client for the MangaDex v5 REST API with per-method retry support."""

    _ALLOWED_CONTENT_RATINGS = ["safe", "suggestive", "erotica", "pornographic"]

    def __init__(
        self,
        client: httpx.AsyncClient,
        rate_limiter: _MangaDexRateLimiter = _shared_rate_limiter,
    ) -> None:
        """Initialise with an ``httpx.AsyncClient`` pre-configured with base URL and auth headers.

        Args:
            client: Pre-configured ``httpx.AsyncClient`` with base URL
                and auth headers.
            rate_limiter: Shared or dedicated rate limiter.  Defaults to
                the module-level singleton so primary and worker clients
                honour the same ceiling.
        """
        self.client = client
        self._rate_limiter = rate_limiter

    async def _get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> httpx.Response:
        """Rate-limit every MangaDex request, including retries and worker traffic."""
        await self._rate_limiter.wait()
        if params is None:
            response = await self.client.get(path)
        else:
            response = await self.client.get(path, params=params)
        retry_after = getattr(response, "headers", {}).get("Retry-After")
        if (
            getattr(response, "status_code", None) == 429
            and retry_after
            and retry_after.isdecimal()
        ):
            await self._rate_limiter.cooldown(
                min(float(retry_after), _MAX_RETRY_AFTER_SECONDS)
            )
        return response

    @with_retry(retryable_status_codes=_RETRYABLE_STATUS_CODES)
    async def search_manga(
        self,
        query: str,
        limit: int = 5,
        offset: int = 0,
        content_ratings: list[str] | None = None,
        demographic: list[str] | None = None,
    ) -> dict[str, Any]:
        """Search manga by title with pagination, content rating, and demographic filters."""
        params: dict[str, Any] = {
            "title": query,
            "limit": limit,
            "offset": offset,
            "includes[]": ["cover_art"],
            "contentRating[]": content_ratings or self._ALLOWED_CONTENT_RATINGS,
        }
        if demographic:
            params["publicationDemographic[]"] = demographic
        response = await self._get(
            "/manga",
            params=params,
        )
        response.raise_for_status()
        return cast("dict[str, Any]", response.json())

    @with_retry(retryable_status_codes=_RETRYABLE_STATUS_CODES)
    async def get_manga(self, manga_id: str) -> dict[str, Any]:
        """Fetch a single manga by its MangaDex UUID, including cover-art relationship."""
        response = await self._get(
            f"/manga/{manga_id}",
            params={
                "includes[]": ["cover_art"],
            },
        )
        response.raise_for_status()
        return cast("dict[str, Any]", response.json())

    @with_retry(retryable_status_codes=_RETRYABLE_STATUS_CODES)
    async def get_chapters(
        self,
        manga_id: str,
        language: str | list[str] | None = "en",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Fetch all chapters for a manga, including scanlation-group relationships."""
        params: dict[str, Any] = {
            "manga": manga_id,
            "includes[]": ["scanlation_group"],
            "order[chapter]": "asc",
            "limit": limit,
            "offset": offset,
            # Include all content ratings — age-gating is handled by the
            # API route's service layer, which checks user age separately.
            # MangaDex default is safe+suggestive only.
            "contentRating[]": ["safe", "suggestive", "erotica", "pornographic"],
        }
        if language is not None:
            params["translatedLanguage[]"] = language
        response = await self._get("/chapter", params=params)
        response.raise_for_status()
        return cast("dict[str, Any]", response.json())

    @with_retry(retryable_status_codes=_RETRYABLE_STATUS_CODES)
    async def get_latest_chapters(
        self, language: str = "en", limit: int = 10
    ) -> dict[str, Any]:
        """Fetch the latest published chapters across all manga, ordered by ``readableAt``."""
        response = await self._get(
            "/chapter",
            params={
                "translatedLanguage[]": language,
                "includes[]": ["scanlation_group"],
                # readableAt yields real currently readable releases.
                "order[readableAt]": "desc",
                "limit": limit,
                "contentRating[]": self._ALLOWED_CONTENT_RATINGS,
            },
        )
        response.raise_for_status()
        return cast("dict[str, Any]", response.json())

    @with_retry(retryable_status_codes=_RETRYABLE_STATUS_CODES)
    async def get_manga_list_by_ids(self, manga_ids: list[str]) -> dict[str, Any]:
        """Bulk-fetch multiple manga by their UUIDs (max 100 per call). Returns cover-art relationships."""
        if not manga_ids:
            return {"data": []}

        response = await self._get(
            "/manga",
            params={
                "ids[]": manga_ids,
                "includes[]": ["cover_art"],
                "limit": min(len(manga_ids), 100),
                # Include all content ratings — see get_chapters comment.
                "contentRating[]": ["safe", "suggestive", "erotica", "pornographic"],
            },
        )
        response.raise_for_status()
        return cast("dict[str, Any]", response.json())

    @with_retry(retryable_status_codes=_RETRYABLE_STATUS_CODES)
    async def get_chapter(self, chapter_id: str) -> dict:
        """Fetch chapter metadata including manga relationship."""
        response = await self._get(f"/chapter/{chapter_id}")
        response.raise_for_status()
        return cast("dict", response.json())

    @with_retry(retryable_status_codes=_RETRYABLE_STATUS_CODES)
    async def get_chapter_pages(self, chapter_id: str) -> dict:
        """Fetch the MangaDex@Home server URLs for a chapter's page images."""
        response = await self._get(f"/at-home/server/{chapter_id}")
        response.raise_for_status()
        return cast("dict", response.json())

    @with_retry(max_retries=1, retryable_status_codes=_RETRYABLE_STATUS_CODES)
    async def get_tags(self) -> dict[str, Any]:
        """Fetch all available manga tags from MangaDex.

        Single retry balances two constraints:
        - Without retry a transient 429/5xx immediately poisons the
          shared cache with the hardcoded fallback (no themes/formats/
          content) for the full cache TTL.
        - The default 3-retry budget (~33s) exceeds the app-level 30s
          request timeout, producing a 504 before the fallback.
        """
        response = await self._get("/manga/tag")
        response.raise_for_status()
        return cast("dict[str, Any]", response.json())

    @with_retry(retryable_status_codes=_RETRYABLE_STATUS_CODES)
    async def list_manga(
        self,
        limit: int,
        offset: int,
        title: str | None = None,
        demographic: list[str] | None = None,
        status: str | None = None,
        order: str | None = None,
        included_tags: list[str] | None = None,
        order_map: dict[str, str] | None = None,
        content_ratings: list[str] | None = None,
    ) -> dict[str, Any]:
        """List manga with filters (title, demographic, status, order, genre tags) and pagination."""
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "includes[]": ["cover_art"],
            "contentRating[]": content_ratings or self._ALLOWED_CONTENT_RATINGS,
        }

        if title:
            params["title"] = title

        if demographic:
            params["publicationDemographic[]"] = demographic

        if status:
            params["status[]"] = status

        # Support both legacy string-based order and direct order_map
        if order:
            if order == "latest":
                params["order[latestUploadedChapter]"] = "desc"
            elif order == "title":
                params["order[title]"] = "asc"
            elif order == "popular":
                params["order[followedCount]"] = "desc"
            elif order == "rating":
                params["order[rating]"] = "desc"

        if order_map:
            for key, value in order_map.items():
                params[f"order[{key}]"] = value

        if included_tags:
            params["includedTags[]"] = included_tags

        response = await self._get("/manga", params=params)
        response.raise_for_status()
        return cast("dict[str, Any]", response.json())

    @with_retry(retryable_status_codes=_RETRYABLE_STATUS_CODES)
    async def get_statistics(self, manga_ids: list[str]) -> dict[str, Any]:
        """Fetch statistics (rating, follows) for multiple manga IDs.

        MangaDex doesn't support bulk - fetches one by one in parallel.
        """
        if not manga_ids:
            return {}

        # Fetch all stats in parallel
        async def fetch_one(manga_id: str) -> tuple[str, dict]:
            try:
                response = await self._get(f"/statistics/manga/{manga_id}")
                response.raise_for_status()
                data = response.json()
                stats = data.get("statistics", {}).get(manga_id, {})
                return manga_id, stats
            except Exception:
                return manga_id, {}

        results = await asyncio.gather(*[fetch_one(mid) for mid in manga_ids])

        # Convert to statistics dict format
        return {"statistics": dict(results)}
