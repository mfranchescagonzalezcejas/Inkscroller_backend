from fastapi import APIRouter, HTTPException
from app.services.chapter_service import ChapterService
from app.models.chapter import Chapter

router = APIRouter(prefix="/chapters", tags=["Chapters"])
service = ChapterService()


@router.get("/manga/{manga_id}", response_model=list[Chapter])
async def get_manga_chapters(manga_id: str, lang: str = "en"):
    manga_id = manga_id.strip()  # 👈 🔥
    chapters = await service.get_chapters(manga_id, language=lang)
    if not chapters:
        raise HTTPException(status_code=404, detail="No chapters found")
    return chapters
