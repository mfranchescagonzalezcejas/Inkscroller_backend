"""Chapter and chapter-page route handlers with age-gated access."""

from typing import cast

from fastapi import APIRouter, Depends, HTTPException

from app.core.age import CONTENT_AGE_LIMITS, can_access_content, can_access_demographic
from app.core.dependencies import (
    get_chapter_pages_service,
    get_chapter_service,
    get_manga_service,
    get_user_age,
    get_user_language,
)
from app.models.chapter import Chapter, ChapterLanguagesResponse
from app.models.home_chapter import HomeChapter
from app.services.chapter_pages_service import ChapterPagesService
from app.services.chapter_service import ChapterService
from app.services.manga_service import MangaService

router = APIRouter(prefix="/chapters", tags=["Chapters"])


@router.get("/latest", response_model=list[HomeChapter])
async def get_latest_home_chapters(
    limit: int = 10,
    lang: str = "en",
    chapter_service: ChapterService = Depends(get_chapter_service),
    user_age: int | None = Depends(get_user_age),
) -> list[HomeChapter]:
    """Return the latest chapters across all manga for the home feed."""
    return cast(
        "list[HomeChapter]",
        await chapter_service.get_latest_home_chapters(
            language=lang, limit=limit, user_age=user_age
        ),
    )


async def _require_manga_access(
    manga_id: str,
    manga_service: MangaService,
    user_age: int | None,
) -> dict:
    """Resolve manga and enforce age gate, returning the accessible manga.

    Raises HTTPException 403 or 404 for denied or unknown manga.
    """
    manga = await manga_service.get_by_id(manga_id, user_age=user_age)
    if manga is None:
        full_manga = await manga_service.get_by_id(manga_id, skip_age_filter=True)
        if full_manga is None:
            raise HTTPException(status_code=404, detail="Manga not found")

        if not can_access_content(
            cast("str | None", full_manga.get("contentRating")), user_age
        ):
            rating = cast("str | None", full_manga.get("contentRating"))
            min_age = CONTENT_AGE_LIMITS.get(rating) if rating is not None else None
            raise HTTPException(
                status_code=403,
                detail=(
                    f"This content is age-restricted (requires {min_age}+)"
                    if min_age is not None
                    else "This content has an unrecognized rating and cannot be accessed"
                ),
            )

        if not can_access_demographic(full_manga.get("demographic"), user_age):
            raise HTTPException(
                status_code=403,
                detail="This manga is age-restricted due to its demographic content",
            )

        raise HTTPException(status_code=404, detail="Manga not found")
    return manga


@router.get("/manga/{manga_id}", response_model=list[Chapter])
async def get_manga_chapters(
    manga_id: str,
    language: str = Depends(get_user_language),
    chapter_service: ChapterService = Depends(get_chapter_service),
    manga_service: MangaService = Depends(get_manga_service),
    user_age: int | None = Depends(get_user_age),
) -> list[Chapter]:
    """Return the chapter list for a manga, gated by the caller's age."""
    await _require_manga_access(manga_id, manga_service, user_age)
    chapters = await chapter_service.get_chapters(manga_id, language=language)
    return cast("list[Chapter]", chapters)


@router.get("/manga/{manga_id}/languages", response_model=ChapterLanguagesResponse)
async def get_manga_chapter_languages(
    manga_id: str,
    preferred_lang: str = "en",
    chapter_service: ChapterService = Depends(get_chapter_service),
    manga_service: MangaService = Depends(get_manga_service),
    user_age: int | None = Depends(get_user_age),
) -> ChapterLanguagesResponse:
    """Discover available languages and return chapters in the best match.

    ``preferred_lang`` is the user's language preference (from frontend).
    Returns available languages, the matched language code, and chapters
    in that matched language — all in one call so the frontend doesn't
    need a second round-trip.
    """
    manga = await _require_manga_access(manga_id, manga_service, user_age)
    available = sorted(manga.get("availableTranslatedLanguages") or [])

    matched = _match_language(preferred_lang, available)
    chapters = cast(
        "list[Chapter]",
        await chapter_service.get_chapters(manga_id, language=matched),
    )

    return ChapterLanguagesResponse(
        available=available,
        matched=matched,
        chapters=chapters,
    )


def _match_language(preferred: str, available: list[str]) -> str:
    """Resolve the best language match from available options.

    1. Exact match → use it.
    2. Prefix match (e.g. ``es`` → ``es-la``) → use the variant.
    3. No match → first available element, or fall back to preferred.
    """
    if not available:
        return preferred

    preferred_lower = preferred.lower()

    # Exact match
    if preferred_lower in available:
        return preferred_lower

    # Prefix match: preferred is a short code, available has a regional variant
    for lang in available:
        if lang.startswith(preferred_lower + "-") or lang.startswith(
            preferred_lower + "_"
        ):
            return lang

    # Fallback to first available
    return available[0]


@router.get("/{chapter_id}/pages")
async def get_chapter_pages(
    chapter_id: str,
    pages_service: ChapterPagesService = Depends(get_chapter_pages_service),
    chapter_service: ChapterService = Depends(get_chapter_service),
    manga_service: MangaService = Depends(get_manga_service),
    user_age: int | None = Depends(get_user_age),
) -> dict:
    """Return MangaDex@Home page image URLs for a chapter, gated by age.

    Resolves the manga from the chapter to check age restrictions
    before returning page URLs.
    """
    chapter_id = chapter_id.strip()

    # Check age restriction by resolving the manga for this chapter
    manga_id = await chapter_service.get_manga_id_for_chapter(chapter_id)
    if not manga_id:
        raise HTTPException(status_code=404, detail="Chapter not found")

    await _require_manga_access(manga_id, manga_service, user_age)
    return await pages_service.get_pages(chapter_id)
