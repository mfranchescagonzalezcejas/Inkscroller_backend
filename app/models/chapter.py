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

    readable: bool
    external: bool
    externalUrl: str | None
