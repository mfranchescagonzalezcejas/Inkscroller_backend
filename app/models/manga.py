"""Pydantic models for manga data and library metadata."""

from pydantic import BaseModel


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
    description: str | None = None
    coverUrl: str | None = None

    demographic: str | None = None
    status: str | None = None

    # Editorial / social (Jikan)
    score: float | None = None
    rank: int | None = None
    popularity: int | None = None
    members: int | None = None
    favorites: int | None = None

    authors: list[str] = []
    serialization: str | None = None

    genres: list[str] = []

    # Lectura (MangaDex)
    chapters: int | None = None

    # Fechas
    startYear: int | None = None
    endYear: int | None = None

    # Content rating (MangaDex)
    contentRating: str | None = None

    # MAL cross-reference (from MangaDex links or Jikan enrichment)
    malId: int | None = None

    # User-library metadata (only present on authenticated library responses)
    library: LibraryMetadata | None = None
