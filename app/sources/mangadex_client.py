import httpx
from typing import Any
import asyncio

from app.core.resilience import with_retry


class MangaDexClient:
    _ALLOWED_CONTENT_RATINGS = ["safe", "suggestive"]

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    @with_retry()
    async def search_manga(self, query: str, limit: int = 5):
        response = await self.client.get(
            "/manga",
            params={
                "title": query,
                "limit": limit,
                "includes[]": ["cover_art"],
                "contentRating[]": self._ALLOWED_CONTENT_RATINGS,
            },
        )
        response.raise_for_status()
        return response.json()

    @with_retry()
    async def get_manga(self, manga_id: str):
        response = await self.client.get(
            f"/manga/{manga_id}",
            params={
                "includes[]": ["cover_art"],
            },
        )
        response.raise_for_status()
        return response.json()

    @with_retry()
    async def get_chapters(
        self,
        manga_id: str,
        language: str = "en",
        limit: int = 100,
    ):
        response = await self.client.get(
            "/chapter",
            params={
                "manga": manga_id,
                "translatedLanguage[]": language,
                "includes[]": ["scanlation_group"],
                "order[chapter]": "asc",
                "limit": limit,
                "contentRating[]": self._ALLOWED_CONTENT_RATINGS,
            },
        )
        response.raise_for_status()
        return response.json()

    @with_retry()
    async def get_latest_chapters(self, language: str = "en", limit: int = 10):
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
        return response.json()

    @with_retry()
    async def get_manga_list_by_ids(self, manga_ids: list[str]):
        if not manga_ids:
            return {"data": []}

        response = await self.client.get(
            "/manga",
            params={
                "ids[]": manga_ids,
                "includes[]": ["cover_art"],
                "limit": min(len(manga_ids), 100),
                "contentRating[]": self._ALLOWED_CONTENT_RATINGS,
            },
        )
        response.raise_for_status()
        return response.json()

    @with_retry()
    async def get_chapter_pages(self, chapter_id: str) -> dict:
        response = await self.client.get(f"/at-home/server/{chapter_id}")
        response.raise_for_status()
        return response.json()

    @with_retry()
    async def list_manga(
        self,
        limit: int,
        offset: int,
        title: str | None = None,
        demographic: str | None = None,
        status: str | None = None,
        order: str | None = None,
        included_tags: list[str] | None = None,
        order_map: dict[str, str] | None = None,
    ):
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "includes[]": ["cover_art"],
            "contentRating[]": self._ALLOWED_CONTENT_RATINGS,
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
        return response.json()

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
