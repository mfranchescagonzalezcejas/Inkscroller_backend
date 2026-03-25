from app.sources.mangadex_client import MangaDexClient
from app.core.cache import SimpleCache
from httpx import HTTPStatusError


class ChapterPagesService:
    def __init__(self, client: MangaDexClient, cache: SimpleCache):
        self._client = client
        self._cache = cache

    async def get_pages(self, chapter_id: str) -> dict:
        chapter_id = chapter_id.strip()
        cache_key = f"pages:{chapter_id}"

        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            payload = await self._client.get_chapter_pages(chapter_id)
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                return {
                    "readable": False,
                    "pages": [],
                    "external": True,
                }
            raise

        base_url = payload.get("baseUrl")
        chapter = payload.get("chapter", {})
        hash_ = chapter.get("hash")
        files = chapter.get("data", [])

        if not base_url or not hash_ or not files:
            return {
                "readable": False,
                "pages": [],
                "external": True,
            }

        pages = [f"{base_url}/data/{hash_}/{file}" for file in files]

        result = {
            "readable": True,
            "external": False,
            "pages": pages,
        }

        self._cache.set(cache_key, result)
        return result
