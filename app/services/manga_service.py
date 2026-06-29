from __future__ import annotations

import logging

from app.sources.mangadex_client import MangaDexClient
from app.core.cache import SimpleCache
from app.sources.jikan_client import JikanClient
from app.services.manga_mapper import map_mangadex_manga, apply_statistics
from app.services.jikan_mapper import map_jikan_detail
from app.core.manga_tags import GENRE_TAG_UUIDS
from app.core.config import settings
from app.core.age import can_access_content

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

    def _filter_by_age(self, manga_list: list[dict], user_age: int | None) -> list[dict]:
        """Filter out manga that the user cannot access due to age restrictions."""
        if user_age is None:
            # Guest or missing birth_date: only safe content
            return [m for m in manga_list if m.get("contentRating") in (None, "safe")]
        return [
            m for m in manga_list
            if can_access_content(m.get("contentRating"), user_age)
        ]

    async def search(self, query: str, limit: int = 5, user_age: int | None = None):
        cache_key = f"search:{query}:{limit}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        payload = await self._client.search_manga(query=query, limit=limit)
        items = payload.get("data", []) if isinstance(payload, dict) else []
        result = [map_mangadex_manga(item) for item in items]
        result = self._filter_by_age(result, user_age)

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
        genre: str | None = None,
        user_age: int | None = None,
    ):
        cache_key = f"manga:list:{limit}:{offset}:{title}:{demographic}:{status}:{order}:{genre}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        # Resolve genre name to MangaDex tag UUID
        included_tags: list[str] | None = None
        if genre:
            tag_uuid = GENRE_TAG_UUIDS.get(genre.lower())
            if tag_uuid:
                included_tags = [tag_uuid]

        payload = await self._client.list_manga(
            limit=limit,
            offset=offset,
            title=title,
            demographic=demographic,
            status=status,
            order=order,
            included_tags=included_tags,
        )

        items = payload.get("data", [])
        total = payload.get("total", 0)

        result = [map_mangadex_manga(item) for item in items]

        # Always fetch statistics to get rating for all manga lists
        if result:
            try:
                manga_ids = [m["id"] for m in result]
                stats_payload = await self._client.get_statistics(manga_ids)
                stats_dict = stats_payload.get("statistics", {})

                # Apply statistics to each manga
                for manga in result:
                    manga_stats = stats_dict.get(manga["id"], {})
                    apply_statistics(manga, manga_stats)
            except Exception:
                logger.warning(
                    "Failed to fetch statistics for manga list, continuing without ratings",
                    exc_info=True,
                )

        result = self._filter_by_age(result, user_age)

        response = {
            "data": result,
            "limit": limit,
            "offset": offset,
            "total": len(result),
        }

        self._cache.set(cache_key, response)
        return response

    async def get_by_id(
        self,
        manga_id: str,
        user_age: int | None = None,
        skip_age_filter: bool = False,
    ):
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

        # Age restriction check (skipped when caller needs raw data for 403 logic)
        if not skip_age_filter and not can_access_content(
            result.get("contentRating"), user_age
        ):
            return None

        # 🔥 Enriquecimiento con Jikan (rellenar huecos) — feature flag
        if not settings.enable_jikan_enrichment:
            self._cache.set(cache_key, result)
            return result

        try:
            jikan_payload = await self._jikan.search_manga(result["title"])
            search_data = jikan_payload.get("data", [])
            jikan_data = (
                map_jikan_detail({"data": search_data[0]}) if search_data else None
            )

            if jikan_data is not None:
                for key, value in jikan_data.items():
                    # Solo rellenamos si MangaDex no tenía el dato
                    if result.get(key) in (None, [], "") and value not in (
                        None,
                        [],
                        "",
                    ):
                        result[key] = value
        except Exception:
            logger.warning(
                "Jikan enrichment failed for manga %s, continuing without it",
                manga_id,
                exc_info=True,
            )

        self._cache.set(cache_key, result)
        return result
