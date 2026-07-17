"""Pydantic model for MangaDex chapter metadata."""

from datetime import datetime

from pydantic import BaseModel


class Chapter(BaseModel):
    """MangaDex chapter metadata.

    ``readable`` indicates whether the chapter has viewable pages on
    MangaDex; ``external`` with ``externalUrl`` means the chapter
    redirects to an official source (e.g. MangaPlus).
    """

    id: str
    number: str | None
    title: str | None
    date: datetime | None
    scanlation_group: str | None = None
    language: str

    readable: bool
    external: bool
    externalUrl: str | None


class ChapterLanguagesResponse(BaseModel):
    """Response for the chapter language discovery endpoint.

    Returns the available languages, the matched language based on the
    user's preference, and the chapters in that matched language.
    """

    available: list[str]
    matched: str
    chapters: list[Chapter]
