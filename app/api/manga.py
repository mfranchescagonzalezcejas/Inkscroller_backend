from fastapi import APIRouter, Depends, HTTPException, Query, Request
import httpx
from app.core.age import CONTENT_AGE_LIMITS, can_access_content
from app.core.dependencies import get_manga_service, get_user_age
from app.core.manga_tags import GENRE_TAG_UUIDS
from app.core.cache import SimpleCache
from app.models.manga import Manga
from app.services.manga_service import MangaService

router = APIRouter(prefix="/manga", tags=["Manga"])
_SUPPORTED_DEMOGRAPHICS = {"shounen", "shoujo", "seinen", "josei", "unspecified"}


def _validate_demographics(
    demographics: list[str] | None, user_age: int | None
) -> list[str] | None:
    """Reject unknown and unauthorized local demographic filter tokens."""
    if not demographics:
        return None
    if any(token not in _SUPPORTED_DEMOGRAPHICS for token in demographics):
        raise HTTPException(status_code=422, detail="Unsupported demographic")
    if "unspecified" in demographics and (user_age is None or user_age < 18):
        raise HTTPException(status_code=403, detail="Unspecified demographic requires 18+")
    return list(dict.fromkeys(demographics))


@router.get("/capabilities")
async def manga_capabilities() -> dict:
    """Advertise the backend contract required for null-demographic filtering."""
    return {
        "demographic_filter": {
            "contract_version": 1,
            "null_union": True,
            "pagination": "cursor-v1",
        }
    }


@router.get("/tags")
async def list_tags(request: Request) -> dict:
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


def _fallback_tags() -> list[dict]:
    """Fallback if MangaDex API is unreachable."""
    return [
        {"id": "423e2eae-a7a2-4a8b-ac03-a8351462d71d", "name": "Romance"},
        {"id": "391b0423-d847-456f-aff0-8b0cfc03066b", "name": "Action"},
    ]


@router.get("/genres")
async def list_genres() -> dict:
    """Returns available genre tags for filtering (legacy endpoint)."""
    return {"genres": list(GENRE_TAG_UUIDS.keys())}


@router.get("/search")
async def search_manga(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    content_rating: str | None = Query(None),
    demographic: list[str] | None = Query(None),
    cursor: str | None = Query(None),
    service: MangaService = Depends(get_manga_service),
    user_age: int | None = Depends(get_user_age),
) -> dict:
    """Search manga by title, filtering results by the caller's age.

    When ``content_rating`` is provided (safe/suggestive/all), it overrides
    the age-based default. Age restrictions still apply — a minor cannot
    escalate access via this parameter.

    Returns a paginated response with ``data``, ``limit``, ``offset``, and
    ``total``, matching the existing ``GET /manga`` contract.
    """
    demographic = _validate_demographics(
        [token for token in demographic if token] if demographic else None,
        user_age,
    )
    kwargs = {
        "limit": limit,
        "offset": offset,
        "user_age": user_age,
        "content_rating": content_rating,
    }
    if demographic is not None:
        kwargs["demographic"] = demographic
    if cursor is not None:
        kwargs["cursor"] = cursor
    try:
        return await service.search(q, **kwargs)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/{manga_id}", response_model=Manga)
async def get_manga(
    manga_id: str,
    service: MangaService = Depends(get_manga_service),
    user_age: int | None = Depends(get_user_age),
):
    """Return manga detail, blocking if the caller is too young."""
    manga_id = manga_id.strip()
    manga = await service.get_by_id(manga_id, user_age=user_age)
    if manga is None:
        # Check if it exists but is blocked by age restriction
        full_manga = await service.get_by_id(manga_id, skip_age_filter=True)
        if full_manga and not can_access_content(
            full_manga.get("contentRating"), user_age
        ):
            min_age = CONTENT_AGE_LIMITS.get(full_manga.get("contentRating"), 0)
            raise HTTPException(
                status_code=403,
                detail=f"This content is age-restricted (requires {min_age}+)",
            )
        raise HTTPException(status_code=404, detail="Manga not found")
    return manga


@router.get("")
async def list_manga(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    title: str | None = None,
    demographic: list[str] | None = Query(None),
    status: str | None = None,
    order: str | None = None,
    order_followed_count: str | None = Query(None, alias="order[followedCount]"),
    order_rating: str | None = Query(None, alias="order[rating]"),
    order_title: str | None = Query(None, alias="order[title]"),
    order_latest: str | None = Query(None, alias="order[latestUploadedChapter]"),
    genre: str | None = None,
    content_rating: str | None = Query(None),
    cursor: str | None = Query(None),
    service: MangaService = Depends(get_manga_service),
    user_age: int | None = Depends(get_user_age),
) -> dict:
    """Return a paginated manga list, filtering results by the caller's age.

    When ``content_rating`` is provided (safe/suggestive/all), it overrides
    the age-based default. Age restrictions still apply — a minor cannot
    escalate access via this parameter.

    Supports ordering, genre and demographic filters.
    """
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

    # ponytail: FastAPI parses ?demographic= as [""] — filter empty entries
    demographic = _validate_demographics(
        [token for token in demographic if token] if demographic else None,
        user_age,
    )

    kwargs = {
        "limit": limit,
        "offset": offset,
        "title": title,
        "demographic": demographic,
        "status": status,
        "order": resolved_order,
        "genre": genre,
        "user_age": user_age,
        "content_rating": content_rating,
    }
    if cursor is not None:
        kwargs["cursor"] = cursor
    try:
        return await service.list_manga(**kwargs)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
