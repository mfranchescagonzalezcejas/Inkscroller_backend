from __future__ import annotations
from typing import Any, Optional
from app.sources.mangadex_client import MangaDexClient
from app.core.cache import SimpleCache
from app.sources.jikan_client import JikanClient

COVER_BASE_URL = "https://uploads.mangadex.org/covers"


def map_mangadex_manga(item: dict[str, Any]) -> dict[str, Any]:
    attributes = item.get("attributes", {})
    relationships = item.get("relationships", [])

    # Title
    titles = attributes.get("title", {})
    title = titles.get("en") or next(iter(titles.values()), "Unknown")

    # Description (base, Jikan la mejorará)
    descriptions = attributes.get("description", {})
    description = descriptions.get("en")

    # Demographic
    demographic = attributes.get("publicationDemographic")

    # Status
    status = attributes.get("status")

    # Cover
    cover_file = None
    for rel in relationships:
        if rel.get("type") == "cover_art":
            cover_file = rel.get("attributes", {}).get("fileName")
            break

    cover_url = (
        f"{COVER_BASE_URL}/{item['id']}/{cover_file}.256.jpg"
        if cover_file
        else None
    )

    return {
        "id": item.get("id"),
        "title": title,
        "description": description,
        "coverUrl": cover_url,
        "demographic": demographic,
        "status": status,

        # ⬇️ EXTRAS (vacíos, Jikan los rellena)
        "genres": [],
        "score": None,
        "rank": None,
        "popularity": None,
        "members": None,
        "favorites": None,
        "authors": [],
        "serialization": None,
        "chapters": None,
        "startYear": None,
        "endYear": None,
    }


def map_jikan_manga(payload: dict[str, Any]) -> dict[str, Any] | None:
    data = payload.get("data", [])
    if not data:
        return None

    manga = data[0]

    demographics = manga.get("demographics") or []
    demographic = demographics[0]["name"].lower() if demographics else None

    return {
        "description": manga.get("synopsis"),
        "status": manga.get("status"),
        "score": manga.get("score"),
        "rank": manga.get("rank"),
        "popularity": manga.get("popularity"),
        "members": manga.get("members"),
        "favorites": manga.get("favorites"),

        "genres": [g["name"].lower() for g in manga.get("genres", [])],
        "authors": [a["name"] for a in manga.get("authors", [])],
        "serialization": (
            manga.get("serializations", [{}])[0].get("name")
            if manga.get("serializations")
            else None
        ),
        "demographic": demographic,

        "startYear": manga.get("published", {}).get("prop", {}).get("from", {}).get("year"),
        "endYear": manga.get("published", {}).get("prop", {}).get("to", {}).get("year"),
    }

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
            print("JIKAN DATA:", jikan_data)


            if jikan_data:
                for key, value in jikan_data.items():
                    # Solo rellenamos si MangaDex no tenía el dato
                    if result.get(key) in (None, [], "") and value not in (None, [], ""):
                        result[key] = value
        except Exception:
            pass  # Jikan nunca debe romper la API

        self._cache.set(cache_key, result)
        return result


