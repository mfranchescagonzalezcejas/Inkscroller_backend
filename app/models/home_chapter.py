from datetime import datetime
from pydantic import BaseModel


class HomeChapter(BaseModel):
    chapterId: str
    mangaId: str
    mangaTitle: str
    mangaCoverUrl: str | None = None
    chapterNumber: str | None = None
    chapterTitle: str | None = None
    scanlation_group: str | None = None
    publishAt: datetime | None = None
    readable: bool
    external: bool
