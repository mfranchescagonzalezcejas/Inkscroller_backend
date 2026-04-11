from fastapi import APIRouter, Depends, HTTPException
from app.core.dependencies import get_chapter_pages_service, get_chapter_service
from app.services.chapter_service import ChapterService
from app.services.chapter_pages_service import ChapterPagesService
from app.models.chapter import Chapter
from app.models.home_chapter import HomeChapter

router = APIRouter(prefix="/chapters", tags=["Chapters"])


@router.get("/latest", response_model=list[HomeChapter])
async def get_latest_home_chapters(
    limit: int = 10,
    lang: str = "en",
    chapter_service: ChapterService = Depends(get_chapter_service),
):
    return await chapter_service.get_latest_home_chapters(language=lang, limit=limit)


@router.get("/manga/{manga_id}", response_model=list[Chapter])
async def get_manga_chapters(
    manga_id: str,
    lang: str = "en",
    chapter_service: ChapterService = Depends(get_chapter_service),
):
    chapters = await chapter_service.get_chapters(manga_id, language=lang)
    if not chapters:
        raise HTTPException(status_code=404, detail="No chapters found")
    return chapters


@router.get("/{chapter_id}/pages")
async def get_chapter_pages(
    chapter_id: str,
    pages_service: ChapterPagesService = Depends(get_chapter_pages_service),
):
    chapter_id = chapter_id.strip()
    return await pages_service.get_pages(chapter_id)
