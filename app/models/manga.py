from pydantic import BaseModel
from typing import List, Optional


class LibraryMetadata(BaseModel):
    """Metadata for a manga saved in the user's library."""

    library_status: str
    added_at: str
    updated_at: str


class Manga(BaseModel):
    """Manga model combining MangaDex fields with optional Jikan enrichment.

    The ``contentRating`` field drives age-gated access control.
    The ``library`` field is only present on authenticated library responses.
    """

    id: str
    title: str
    description: Optional[str] = None
    coverUrl: Optional[str] = None

    demographic: Optional[str] = None
    status: Optional[str] = None

    # Editorial / social (Jikan)
    score: Optional[float] = None
    rank: Optional[int] = None
    popularity: Optional[int] = None
    members: Optional[int] = None
    favorites: Optional[int] = None

    authors: List[str] = []
    serialization: Optional[str] = None

    genres: List[str] = []

    # Lectura (MangaDex)
    chapters: Optional[int] = None

    # Fechas
    startYear: Optional[int] = None
    endYear: Optional[int] = None

    # Content rating (MangaDex)
    contentRating: Optional[str] = None

    # User-library metadata (only present on authenticated library responses)
    library: Optional[LibraryMetadata] = None
