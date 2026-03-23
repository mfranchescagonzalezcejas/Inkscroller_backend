from __future__ import annotations
from typing import Optional
from app.sources.mangadex_client import MangaDexClient
from app.core.cache import SimpleCache
from app.sources.jikan_client import JikanClient
from app.services.manga_mapper import map_mangadex_manga, map_jikan_manga


class MangaService:
    def __init__(
        self,
        client: Optional[MangaDexClient] = None,
        jikan: Optional[JikanClient] = None,
    ):
        self._client = client or MangaDexClient()
        self._jikan = jikan or JikanClient()
        self._cache = SimpleCache(ttl_seconds=300)  # 5 minutos

    async def search(self, query: str, limit: int = 5):
        cache_key = f"search:{query}:{limit}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        payload = await self._client.search_manga(query=query, limit=limit)
        items = payload.get("data", []) if isinstance(payload, dict) else []
        result = [map_mangadex_manga(item) for item in items]

        self._cache.set(cache_key, result)
        return result
    
    async def list_manga(
        self,
        limit: int = 20,
        offset: int = 0,
        title: str | None = None,
        demographic: str | None = None,
        status: str | None = None,
        order: str | None = None,
    ):
        cache_key = f"manga:list:{limit}:{offset}:{title}:{demographic}:{status}:{order}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        payload = await self._client.list_manga(
            limit=limit,
            offset=offset,
            title=title,
            demographic=demographic,
            status=status,
            order=order,
        )

        items = payload.get("data", [])
        total = payload.get("total", 0)

        result = [map_mangadex_manga(item) for item in items]

        response = {
            "data": result,
            "limit": limit,
            "offset": offset,
            "total": total,
        }

        self._cache.set(cache_key, response)
        return response

    async def get_by_id(self, manga_id: str):
        cache_key = f"manga:{manga_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        payload = await self._client.get_manga(manga_id)
        item = payload.get("data")
        if not item:
            return None

        # Base MangaDex
        result = map_mangadex_manga(item)

        # 🔥 Enriquecimiento con Jikan (rellenar huecos)
        try:
            jikan_payload = await self._jikan.search_manga(result["title"])
            jikan_data = map_jikan_manga(jikan_payload)

            if jikan_data:
                for key, value in jikan_data.items():
                    # Solo rellenamos si MangaDex no tenía el dato
                    if result.get(key) in (None, [], "") and value not in (None, [], ""):
                        result[key] = value
        except Exception:
            pass  # Jikan nunca debe romper la API

        self._cache.set(cache_key, result)
        return result


