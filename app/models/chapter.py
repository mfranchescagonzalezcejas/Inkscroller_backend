from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Chapter(BaseModel):
    """MangaDex chapter metadata.

    ``readable`` indicates whether the chapter has viewable pages on
    MangaDex; ``external`` with ``externalUrl`` means the chapter
    redirects to an official source (e.g. MangaPlus).
    """
    id: str
    number: Optional[str]
    title: Optional[str]
    date: Optional[datetime]
    scanlation_group: Optional[str] = None

    readable: bool
    external: bool
    externalUrl: Optional[str]
