from typing import List
from app.sources.mangadex_client import MangaDexClient
from app.core.cache import SimpleCache
from app.services.chapter_mapper import map_mangadex_chapter


class ChapterService:
    def __init__(self, client: MangaDexClient, cache: SimpleCache):
        self._client = client
        self._cache = cache

    async def get_chapters(
        self,
        manga_id: str,
        language: str = "en",
    ) -> List[dict]:
        cache_key = f"chapters:{manga_id}:{language}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        payload = await self._client.get_chapters(
            manga_id=manga_id,
            language=language,
        )

        items = payload.get("data", [])
        result = [
            map_mangadex_chapter(item)
            for item in items
            if (
                item.get("attributes", {}).get("pages", 0) > 0
                or item.get("attributes", {}).get("externalUrl") is not None
                )
            ]

        self._cache.set(cache_key, result)
        return result
