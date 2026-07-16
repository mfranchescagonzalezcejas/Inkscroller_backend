"""Pydantic model for the home-page chapter feed entries."""

from datetime import datetime

from pydantic import BaseModel


class HomeChapter(BaseModel):
    """A chapter entry displayed on the home page, enriched with manga title and cover URL."""

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
