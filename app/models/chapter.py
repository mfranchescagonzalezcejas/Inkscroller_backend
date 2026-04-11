from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Chapter(BaseModel):
    id: str
    number: Optional[str]
    title: Optional[str]
    date: Optional[datetime]
    scanlation_group: Optional[str] = None

    readable: bool
    external: bool
    externalUrl: Optional[str]
