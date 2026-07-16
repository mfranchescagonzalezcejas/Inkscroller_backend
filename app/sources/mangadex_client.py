"""HTTP client for the MangaDex v5 REST API with per-method retry support."""

import asyncio
from typing import Any, cast

import httpx
from app.core.resilience import with_retry


class MangaDexClient:
    """HTTP client for the MangaDex v5 REST API with per-method retry support."""

    _ALLOWED_CONTENT_RATINGS = ["safe", "suggestive", "erotica", "pornographic"]

    def __init__(self, client: httpx.AsyncClient):
        """Initialise with an ``httpx.AsyncClient`` pre-configured with base URL and auth headers."""
        self.client = client

    @with_retry()
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
        response = await self.client.get(
            "/manga",
            params=params,
        )
        response.raise_for_status()
        return cast("dict[str, Any]", response.json())

    @with_retry()
    async def get_manga(self, manga_id: str) -> dict[str, Any]:
        """Fetch a single manga by its MangaDex UUID, including cover-art relationship."""
        response = await self.client.get(
            f"/manga/{manga_id}",
            params={
                "includes[]": ["cover_art"],
            },
        )
        response.raise_for_status()
        return cast("dict[str, Any]", response.json())

    @with_retry()
    async def get_chapters(
        self,
        manga_id: str,
        language: str = "en",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Fetch all chapters for a manga, including scanlation-group relationships."""
        response = await self.client.get(
            "/chapter",
            params={
                "manga": manga_id,
                "translatedLanguage[]": language,
                "includes[]": ["scanlation_group"],
                "order[chapter]": "asc",
                "limit": limit,
                "offset": offset,
                # Include all content ratings — age-gating is handled by the
                # API route's service layer, which checks user age separately.
                # MangaDex default is safe+suggestive only.
                "contentRating[]": ["safe", "suggestive", "erotica", "pornographic"],
            },
        )
        response.raise_for_status()
        return cast("dict[str, Any]", response.json())

    @with_retry()
    async def get_latest_chapters(
        self, language: str = "en", limit: int = 10
    ) -> dict[str, Any]:
        """Fetch the latest published chapters across all manga, ordered by ``readableAt``."""
        response = await self.client.get(
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

    @with_retry()
    async def get_manga_list_by_ids(self, manga_ids: list[str]) -> dict[str, Any]:
        """Bulk-fetch multiple manga by their UUIDs (max 100 per call). Returns cover-art relationships."""
        if not manga_ids:
            return {"data": []}

        response = await self.client.get(
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

    @with_retry()
    async def get_chapter(self, chapter_id: str) -> dict:
        """Fetch chapter metadata including manga relationship."""
        response = await self.client.get(f"/chapter/{chapter_id}")
        response.raise_for_status()
        return cast("dict", response.json())

    @with_retry()
    async def get_chapter_pages(self, chapter_id: str) -> dict:
        """Fetch the MangaDex@Home server URLs for a chapter's page images."""
        response = await self.client.get(f"/at-home/server/{chapter_id}")
        response.raise_for_status()
        return cast("dict", response.json())

    @with_retry(max_retries=1)
    async def get_tags(self) -> dict[str, Any]:
        """Fetch all available manga tags from MangaDex.

        Single retry balances two constraints:
        - Without retry a transient 429/5xx immediately poisons the
          shared cache with the hardcoded fallback (no themes/formats/
          content) for the full cache TTL.
        - The default 3-retry budget (~33s) exceeds the app-level 30s
          request timeout, producing a 504 before the fallback.
        """
        response = await self.client.get("/manga/tag")
        response.raise_for_status()
        return cast("dict[str, Any]", response.json())

    @with_retry()
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

        response = await self.client.get("/manga", params=params)
        response.raise_for_status()
        return cast("dict[str, Any]", response.json())

    @with_retry()
    async def get_statistics(self, manga_ids: list[str]) -> dict[str, Any]:
        """Fetch statistics (rating, follows) for multiple manga IDs.

        MangaDex doesn't support bulk - fetches one by one in parallel.
        """
        if not manga_ids:
            return {}

        # Fetch all stats in parallel
        async def fetch_one(manga_id: str) -> tuple[str, dict]:
            try:
                response = await self.client.get(f"/statistics/manga/{manga_id}")
                response.raise_for_status()
                data = response.json()
                stats = data.get("statistics", {}).get(manga_id, {})
                return manga_id, stats
            except Exception:
                return manga_id, {}

        results = await asyncio.gather(*[fetch_one(mid) for mid in manga_ids])

        # Convert to statistics dict format
        return {"statistics": dict(results)}
