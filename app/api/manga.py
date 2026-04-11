from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import List
import httpx
from app.core.dependencies import get_manga_service
from app.core.manga_tags import GENRE_TAG_UUIDS
from app.core.cache import SimpleCache
from app.models.manga import Manga
from app.services.manga_service import MangaService

router = APIRouter(prefix="/manga", tags=["Manga"])


@router.get("/tags")
async def list_tags(request: Request):
    """
    Returns all available tags from MangaDex, grouped by type.

    Groups: genre, theme, format, content
    Each tag has: id (UUID), name (en), group

    Cached for 1 hour to avoid hitting MangaDex API on every request.
    """
    cache: SimpleCache = request.app.state.cache
    cache_key = "mangadex:tags"

    # Check cache first
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.mangadex.org/manga/tag",
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        # Fallback to hardcoded tags if MangaDex is unreachable
        fallback = {
            "genres": _fallback_tags(),
            "themes": [],
            "formats": [],
            "content": [],
        }
        cache.set(cache_key, fallback)
        return fallback

    collection = data.get("data", [])

    # Group tags by their group attribute
    grouped = {
        "genres": [],
        "themes": [],
        "formats": [],
        "content": [],
    }

    for tag in collection:
        attrs = tag.get("attributes", {})
        name = attrs.get("name", {}).get("en", "")
        group = attrs.get("group", "")

        tag_info = {
            "id": tag["id"],
            "name": name,
        }

        if group == "genre":
            grouped["genres"].append(tag_info)
        elif group == "theme":
            grouped["themes"].append(tag_info)
        elif group == "format":
            grouped["formats"].append(tag_info)
        elif group == "content":
            grouped["content"].append(tag_info)

    # Cache for 1 hour (3600 seconds) - tags don't change often
    cache.set(cache_key, grouped)

    return grouped


def _fallback_tags():
    """Fallback if MangaDex API is unreachable."""
    return [
        {"id": "423e2eae-a7a2-4a8b-ac03-a8351462d71d", "name": "Romance"},
        {"id": "391b0423-d847-456f-aff0-8b0cfc03066b", "name": "Action"},
    ]


@router.get("/genres")
async def list_genres():
    """Returns available genre tags for filtering (legacy endpoint)."""
    return {"genres": list(GENRE_TAG_UUIDS.keys())}


@router.get("/search", response_model=List[Manga])
async def search_manga(
    q: str = Query(..., min_length=1),
    service: MangaService = Depends(get_manga_service),
):
    return await service.search(q)


@router.get("/{manga_id}", response_model=Manga)
async def get_manga(
    manga_id: str,
    service: MangaService = Depends(get_manga_service),
):
    manga_id = manga_id.strip()
    manga = await service.get_by_id(manga_id)
    if manga is None:
        raise HTTPException(status_code=404, detail="Manga not found")
    return manga


@router.get("")
async def list_manga(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    title: str | None = None,
    demographic: str | None = None,
    status: str | None = None,
    order: str | None = None,
    order_followed_count: str | None = Query(None, alias="order[followedCount]"),
    order_rating: str | None = Query(None, alias="order[rating]"),
    order_title: str | None = Query(None, alias="order[title]"),
    order_latest: str | None = Query(None, alias="order[latestUploadedChapter]"),
    genre: str | None = None,
    service: MangaService = Depends(get_manga_service),
):
    resolved_order = order
    if resolved_order is None:
        if order_followed_count == "desc":
            resolved_order = "popular"
        elif order_rating == "desc":
            resolved_order = "rating"
        elif order_title == "asc":
            resolved_order = "title"
        elif order_latest == "desc":
            resolved_order = "latest"

    return await service.list_manga(
        limit=limit,
        offset=offset,
        title=title,
        demographic=demographic,
        status=status,
        order=resolved_order,
        genre=genre,
    )
