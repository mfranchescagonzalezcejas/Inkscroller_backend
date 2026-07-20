"""Manga catalogue route handlers with search, list, detail, and age-gated access."""

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.age import CONTENT_AGE_LIMITS, can_access_content
from app.core.config import settings
from app.core.dependencies import get_manga_service, get_tag_service, get_user_age
from app.core.exceptions import PreferencesValidationError
from app.core.manga_tags import GENRE_TAG_UUIDS
from app.models.manga import Manga
from app.services.manga_service import MangaService
from app.services.tag_service import TagService

router = APIRouter(prefix="/manga", tags=["Manga"])
_SUPPORTED_DEMOGRAPHICS = {"shounen", "shoujo", "seinen", "josei", "unspecified"}


def _validate_demographics(
    demographics: list[str] | None,
) -> list[str] | None:
    """Reject unknown demographic filter tokens."""
    if not demographics:
        return None
    if any(token not in _SUPPORTED_DEMOGRAPHICS for token in demographics):
        raise PreferencesValidationError("Unsupported demographic")
    return list(dict.fromkeys(demographics))


@router.get("/capabilities")
async def manga_capabilities() -> dict:
    """Advertise the backend contract required for null-demographic filtering."""
    pagination = "cursor-v1" if settings.cursor_secret else "offset"
    return {
        "demographic_filter": {
            "contract_version": 1,
            "null_union": True,
            "pagination": pagination,
        }
    }


@router.get("/tags")
async def list_tags(service: TagService = Depends(get_tag_service)) -> dict:
    """Return all available tags from MangaDex, grouped by type.

    Groups: genre, theme, format, content
    Each tag has: id (UUID), name (en)
    """
    return await service.get_tags()


@router.get("/genres")
async def list_genres() -> dict:
    """Return available genre tags for filtering (legacy endpoint)."""
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
    )
    try:
        return await service.search(
            q,
            limit=limit,
            offset=offset,
            user_age=user_age,
            content_rating=content_rating,
            demographic=demographic,
            cursor=cursor,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/{manga_id}", response_model=Manga)
async def get_manga(
    manga_id: str,
    language: str | None = Query(None, min_length=2, max_length=10),
    service: MangaService = Depends(get_manga_service),
    user_age: int | None = Depends(get_user_age),
) -> Manga:
    """Return manga detail, blocking if the caller is too young.

    Optionally specify ``language`` (e.g. ``es``, ``ja``) to get the
    title and description in that language. Falls back to English then
    to the first available value.
    """
    manga_id = manga_id.strip()
    manga = await service.get_by_id(manga_id, user_age=user_age, language=language)
    if manga is None:
        # Check if it exists but is blocked by age restriction
        full_manga = await service.get_by_id(manga_id, skip_age_filter=True)
        if full_manga and not can_access_content(
            cast("str | None", full_manga.get("contentRating")), user_age
        ):
            rating = cast("str | None", full_manga.get("contentRating"))
            min_age = CONTENT_AGE_LIMITS.get(rating) if rating is not None else 0
            raise HTTPException(
                status_code=403,
                detail=f"This content is age-restricted (requires {min_age}+)",
            )
        raise HTTPException(status_code=404, detail="Manga not found")
    return cast("Manga", manga)


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
    )

    try:
        return await service.list_manga(
            limit=limit,
            offset=offset,
            title=title,
            demographic=demographic,
            status=status,
            order=resolved_order,
            genre=genre,
            user_age=user_age,
            content_rating=content_rating,
            cursor=cursor,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
