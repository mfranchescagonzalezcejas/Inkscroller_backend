"""Service for retrieving and grouping MangaDex tags with caching and fallback."""

from typing import Any, cast

from app.core.cache import SimpleCache
from app.core.manga_tags import GENRE_TAG_UUIDS
from app.sources.mangadex_client import MangaDexClient

_CACHE_KEY = "mangadex:tags"
_GROUP_MAP = {
    "genre": "genres",
    "theme": "themes",
    "format": "formats",
    "content": "content",
}


class TagService:
    """Orchestrates cache-first MangaDex tag retrieval, grouping, and fallback."""

    def __init__(self, client: MangaDexClient, cache: SimpleCache) -> None:
        """Initialise with a MangaDex client and shared cache."""
        self._client = client
        self._cache = cache

    async def get_tags(self) -> dict[str, list[dict[str, str]]]:
        """Return grouped tags, using the cache or falling back to MangaDex."""
        cached = self._cache.get(_CACHE_KEY)
        if cached is not None:
            return cast("dict[str, list[dict[str, str]]]", cached)

        try:
            data = await self._client.get_tags()
            grouped = self._group_tags(data)
        except Exception:
            grouped = self._fallback_tags()

        self._cache.set(_CACHE_KEY, grouped)
        return grouped

    @staticmethod
    def _group_tags(data: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
        """Map MangaDex tag records into genres/themes/formats/content buckets."""
        grouped: dict[str, list[dict[str, str]]] = {
            "genres": [],
            "themes": [],
            "formats": [],
            "content": [],
        }

        for tag in data.get("data", []):
            attrs = tag.get("attributes", {})
            name = attrs.get("name", {}).get("en", "")
            group = attrs.get("group", "")
            target = _GROUP_MAP.get(group)
            if target is None:
                continue
            grouped[target].append({"id": tag["id"], "name": name})

        return grouped

    @staticmethod
    def _fallback_tags() -> dict[str, list[dict[str, str]]]:
        """Return the configured fallback genres when MangaDex is unreachable."""
        genres: list[dict[str, str]] = []
        for slug, tag_id in GENRE_TAG_UUIDS.items():
            if slug == "sci-fi":
                name = "Sci-fi"
            elif slug == "slice-of-life":
                name = "Slice of Life"
            else:
                name = slug.replace("-", " ").title()
            genres.append({"id": tag_id, "name": name})

        return {
            "genres": genres,
            "themes": [],
            "formats": [],
            "content": [],
        }
