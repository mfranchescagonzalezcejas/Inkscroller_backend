from fastapi import APIRouter, Depends, HTTPException
from app.core.age import CONTENT_AGE_LIMITS, can_access_content
from app.core.dependencies import (
    get_chapter_pages_service,
    get_chapter_service,
    get_manga_service,
    get_user_age,
)
from app.services.chapter_service import ChapterService
from app.services.chapter_pages_service import ChapterPagesService
from app.services.manga_service import MangaService
from app.models.chapter import Chapter
from app.models.home_chapter import HomeChapter

router = APIRouter(prefix="/chapters", tags=["Chapters"])


@router.get("/latest", response_model=list[HomeChapter])
async def get_latest_home_chapters(
    limit: int = 10,
    lang: str = "en",
    chapter_service: ChapterService = Depends(get_chapter_service),
):
    """Return the latest chapters across all manga for the home feed."""
    return await chapter_service.get_latest_home_chapters(language=lang, limit=limit)


@router.get("/manga/{manga_id}", response_model=list[Chapter])
async def get_manga_chapters(
    manga_id: str,
    lang: str = "en",
    chapter_service: ChapterService = Depends(get_chapter_service),
    manga_service: MangaService = Depends(get_manga_service),
    user_age: int | None = Depends(get_user_age),
):
    """Return the chapter list for a manga, gated by the caller's age."""
    # Check age restriction
    manga = await manga_service.get_by_id(manga_id, user_age=user_age)
    if manga is None:
        full_manga = await manga_service.get_by_id(manga_id, skip_age_filter=True)
        if full_manga and not can_access_content(
            full_manga.get("contentRating"), user_age
        ):
            rating = full_manga.get("contentRating")
            min_age = CONTENT_AGE_LIMITS.get(rating)
            raise HTTPException(
                status_code=403,
                detail=(
                    f"This content is age-restricted (requires {min_age}+)"
                    if min_age is not None
                    else "This content has an unrecognized rating and cannot be accessed"
                ),
            )
        raise HTTPException(status_code=404, detail="Manga not found")

    chapters = await chapter_service.get_chapters(manga_id, language=lang)
    if not chapters:
        raise HTTPException(status_code=404, detail="No chapters found")
    return chapters


@router.get("/{chapter_id}/pages")
async def get_chapter_pages(
    chapter_id: str,
    pages_service: ChapterPagesService = Depends(get_chapter_pages_service),
    chapter_service: ChapterService = Depends(get_chapter_service),
    manga_service: MangaService = Depends(get_manga_service),
    user_age: int | None = Depends(get_user_age),
):
    """Return MangaDex@Home page image URLs for a chapter, gated by age.

    Resolves the manga from the chapter to check age restrictions
    before returning page URLs.
    """
    chapter_id = chapter_id.strip()

    # Check age restriction by resolving the manga for this chapter
    manga_id = await chapter_service.get_manga_id_for_chapter(chapter_id)
    if not manga_id:
        raise HTTPException(status_code=404, detail="Chapter not found")

    manga = await manga_service.get_by_id(manga_id, user_age=user_age)
    if manga is None:
        full_manga = await manga_service.get_by_id(manga_id, skip_age_filter=True)
        if full_manga and not can_access_content(
            full_manga.get("contentRating"), user_age
        ):
            rating = full_manga.get("contentRating")
            min_age = CONTENT_AGE_LIMITS.get(rating)
            raise HTTPException(
                status_code=403,
                detail=(
                    f"This content is age-restricted (requires {min_age}+)"
                    if min_age is not None
                    else "This content has an unrecognized rating and cannot be accessed"
                ),
            )
        raise HTTPException(status_code=404, detail="Manga not found")

    return await pages_service.get_pages(chapter_id)
