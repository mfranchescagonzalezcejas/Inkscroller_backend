from fastapi import APIRouter, HTTPException
from app.services.chapter_service import ChapterService
from app.services.chapter_pages_service import ChapterPagesService
from app.models.chapter import Chapter

router = APIRouter(prefix="/chapters", tags=["Chapters"])
chapter_service = ChapterService()
pages_service = ChapterPagesService()


@router.get("/manga/{manga_id}", response_model=list[Chapter])
async def get_manga_chapters(manga_id: str, lang: str = "en"):
    chapters = await chapter_service.get_chapters(manga_id, language=lang)
    if not chapters:
        raise HTTPException(status_code=404, detail="No chapters found")
    return chapters


@router.get("/{chapter_id}/pages")
async def get_chapter_pages(chapter_id: str):
    chapter_id = chapter_id.strip()
    return await pages_service.get_pages(chapter_id)
