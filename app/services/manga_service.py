from __future__ import annotations

import logging
from typing import Optional

from app.sources.mangadex_client import MangaDexClient
from app.core.cache import SimpleCache
from app.sources.jikan_client import JikanClient
from app.services.manga_mapper import map_mangadex_manga
from app.services.jikan_mapper import map_jikan_detail

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class MangaService:
    def __init__(
        self,
        client: MangaDexClient,
        jikan: JikanClient,
        cache: SimpleCache,
    ):
        self._client = client
        self._jikan = jikan
        self._cache = cache

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
            search_data = jikan_payload.get("data", [])
            jikan_data = map_jikan_detail({"data": search_data[0]}) if search_data else None

            if jikan_data is not None:
                for key, value in jikan_data.items():
                    # Solo rellenamos si MangaDex no tenía el dato
                    if result.get(key) in (None, [], "") and value not in (None, [], ""):
                        result[key] = value
        except Exception:
            logger.warning(
                "Jikan enrichment failed for manga %s, continuing without it",
                manga_id,
                exc_info=True,
            )

        self._cache.set(cache_key, result)
        return result


