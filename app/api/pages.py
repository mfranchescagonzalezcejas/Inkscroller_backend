from fastapi import APIRouter
from app.services.chapter_pages_service import ChapterPagesService

router = APIRouter(prefix="/chapters", tags=["Pages"])
service = ChapterPagesService()


@router.get("/{chapter_id}/pages")
async def get_chapter_pages(chapter_id: str):
    chapter_id = chapter_id.strip()
    return await service.get_pages(chapter_id)
