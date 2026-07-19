"""Users router - authenticated endpoints for profile, reading preferences and library."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.age import can_access_content
from app.core.dependencies import (
    get_current_user,
    get_current_user_no_bootstrap,
    get_current_user_verified,
    get_manga_service,
    get_user_age,
    get_user_service,
)
from app.core.firebase_auth import FirebaseTokenPayload
from app.models.manga import LibraryMetadata, Manga
from app.models.user import (
    AddToLibraryRequest,
    ReadingPreferences,
    UpdateLibraryStatusRequest,
    UpdatePreferencesRequest,
    UpdateReadingProgressRequest,
    UpdateUserProfileRequest,
    UserProfile,
)
from app.services.manga_service import MangaService
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])

logger = logging.getLogger(__name__)


@router.get("/me", response_model=UserProfile)
async def get_me(
    current_user: FirebaseTokenPayload = Depends(get_current_user_verified),
    user_service: UserService = Depends(get_user_service),
) -> UserProfile:
    """Return the local profile for the authenticated (email-verified) Firebase user.

    Requires email verification — 403 if the Firebase account email is unverified.
    """
    return await user_service.get_or_create_user(current_user)


@router.patch("/me", response_model=UserProfile)
async def update_me(
    body: UpdateUserProfileRequest,
    current_user: FirebaseTokenPayload = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserProfile:
    """Update username and birth date for the authenticated account profile."""
    await user_service.get_or_create_user(current_user)
    return await user_service.update_profile_metadata(current_user.uid, body)


@router.delete("/me", status_code=204)
async def delete_me(
    current_user: FirebaseTokenPayload = Depends(get_current_user_no_bootstrap),
    user_service: UserService = Depends(get_user_service),
) -> None:
    """Delete the authenticated account and all associated data.

    Uses a lightweight token-only check so users can delete accounts even
    before the local row is bootstrapped.
    """
    await user_service.delete_account(current_user.uid)


@router.get("/me/preferences", response_model=ReadingPreferences)
async def get_preferences(
    current_user: FirebaseTokenPayload = Depends(get_current_user_verified),
    user_service: UserService = Depends(get_user_service),
) -> ReadingPreferences:
    """Return the reading preferences for the authenticated (email-verified) user."""
    return await user_service.get_preferences(current_user.uid)


@router.put("/me/preferences", response_model=ReadingPreferences)
async def update_preferences(
    body: UpdatePreferencesRequest,
    current_user: FirebaseTokenPayload = Depends(get_current_user_verified),
    user_service: UserService = Depends(get_user_service),
) -> ReadingPreferences:
    """Update and return the reading preferences for the authenticated (email-verified) user."""
    return await user_service.update_preferences(current_user.uid, body)


# ── Library ───────────────────────────────────────────────────────────────────


# Mapping from manga_service.get_by_id() camelCase keys to entry snake_case keys.
_CAMEL_TO_SNAKE = {
    "startYear": "start_year",
    "endYear": "end_year",
    "malId": "mal_id",
}


@router.get("/me/library", response_model=list[Manga])
async def get_library(
    current_user: FirebaseTokenPayload = Depends(get_current_user_verified),
    user_service: UserService = Depends(get_user_service),
    manga_service: MangaService = Depends(get_manga_service),
    user_age: int | None = Depends(get_user_age),
) -> list[Manga]:
    """Return the user's library from cached SQLite data — email verification required."""
    entries = await user_service.get_library_entries(current_user.uid)

    # Lazy enrichment: entries with NULL score haven't been enriched yet.
    # Fetch from MangaDex on read and backfill the entry dict in place.
    for entry in entries:
        if entry.get("score") is not None:
            continue
        enriched = await manga_service.get_by_id(
            entry["manga_id"], skip_age_filter=True
        )
        if not enriched:
            continue
        for camel, snake in _CAMEL_TO_SNAKE.items():
            val = enriched.get(camel)
            if val is not None:
                entry[snake] = val
        for key in (
            "title",
            "description",
            "demographic",
            "status",
            "score",
            "rank",
            "popularity",
            "members",
            "favorites",
            "serialization",
            "chapters",
        ):
            val = enriched.get(key)
            if val is not None:
                entry[key] = val
        if enriched.get("authors"):
            entry["authors"] = enriched["authors"]
        if enriched.get("genres"):
            entry["genres"] = enriched["genres"]
        # Map enriched "type" (from mapper) to DB column "manga_type"
        manga_type_val = enriched.get("type")
        if manga_type_val is not None:
            entry["manga_type"] = manga_type_val

        # Persist the enriched data back to user_library so subsequent
        # reads are fast and don't depend on the lazy enrichment path.
        await user_service.add_to_library(
            current_user.uid,
            entry["manga_id"],
            title=entry.get("title"),
            cover_url=entry.get("cover_url"),
            authors=entry.get("authors"),
            content_rating=entry.get("content_rating"),
            description=entry.get("description"),
            demographic=entry.get("demographic"),
            status=entry.get("status"),
            score=entry.get("score"),
            rank=entry.get("rank"),
            popularity=entry.get("popularity"),
            members=entry.get("members"),
            favorites=entry.get("favorites"),
            serialization=entry.get("serialization"),
            genres=entry.get("genres"),
            chapters=entry.get("chapters"),
            start_year=entry.get("start_year"),
            end_year=entry.get("end_year"),
            mal_id=entry.get("mal_id"),
            manga_type=entry.get("manga_type"),
        )

    # Filter by age
    filtered = []
    for entry in entries:
        rating = entry.get("content_rating")
        if can_access_content(rating, user_age):
            filtered.append(entry)
    return [
        Manga(
            id=entry["manga_id"],
            title=entry["title"] or entry["manga_id"],
            type=entry.get("manga_type"),
            description=entry["description"],
            coverUrl=entry["cover_url"],
            demographic=entry["demographic"],
            status=entry["status"],
            score=entry["score"],
            rank=entry["rank"],
            popularity=entry["popularity"],
            members=entry["members"],
            favorites=entry["favorites"],
            authors=entry["authors"],
            serialization=entry["serialization"],
            genres=entry["genres"],
            chapters=entry["chapters"],
            startYear=entry["start_year"],
            endYear=entry["end_year"],
            contentRating=entry["content_rating"],
            malId=entry["mal_id"],
            library=LibraryMetadata(
                library_status=entry["library_status"],
                chapters_read=entry.get("chapters_read", 0),
                added_at=entry["added_at"],
                updated_at=entry["updated_at"],
            ),
        )
        for entry in filtered
    ]


@router.post("/me/library/{manga_id}", status_code=204)
async def add_to_library(
    manga_id: str,
    body: AddToLibraryRequest = AddToLibraryRequest(),
    current_user: FirebaseTokenPayload = Depends(get_current_user_verified),
    user_service: UserService = Depends(get_user_service),
    manga_service: MangaService = Depends(get_manga_service),
) -> None:
    """Save a manga to the authenticated user's library, caching its metadata."""
    # Persist metadata from the authoritative MangaDex response.
    manga = await manga_service.get_by_id(manga_id, skip_age_filter=True)

    await user_service.add_to_library(
        current_user.uid,
        manga_id,
        title=manga.get("title") if manga else None,
        cover_url=manga.get("coverUrl") if manga else None,
        authors=manga.get("authors") if manga else None,
        content_rating=manga.get("contentRating") if manga else None,
        description=manga.get("description") if manga else None,
        demographic=manga.get("demographic") if manga else None,
        status=manga.get("status") if manga else None,
        score=manga.get("score") if manga else None,
        rank=manga.get("rank") if manga else None,
        popularity=manga.get("popularity") if manga else None,
        members=manga.get("members") if manga else None,
        favorites=manga.get("favorites") if manga else None,
        serialization=manga.get("serialization") if manga else None,
        genres=manga.get("genres") if manga else None,
        chapters=manga.get("chapters") if manga else None,
        start_year=manga.get("startYear") if manga else None,
        end_year=manga.get("endYear") if manga else None,
        mal_id=manga.get("malId") if manga else None,
        manga_type=manga.get("type") if manga else None,
    )


@router.patch("/me/library/{manga_id}", response_model=LibraryMetadata)
async def update_library_status(
    manga_id: str,
    body: UpdateLibraryStatusRequest,
    current_user: FirebaseTokenPayload = Depends(get_current_user_verified),
    user_service: UserService = Depends(get_user_service),
) -> LibraryMetadata:
    """Update library status for a saved manga and return updated metadata."""
    updated = await user_service.update_library_status(
        current_user.uid, manga_id, body.library_status
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Manga not in library")

    return LibraryMetadata(
        library_status=updated["library_status"],
        chapters_read=int(updated.get("chapters_read", 0)),
        added_at=updated["added_at"],
        updated_at=updated["updated_at"],
    )


@router.patch("/me/library/{manga_id}/progress", response_model=LibraryMetadata)
async def update_reading_progress(
    manga_id: str,
    body: UpdateReadingProgressRequest,
    current_user: FirebaseTokenPayload = Depends(get_current_user_verified),
    user_service: UserService = Depends(get_user_service),
) -> LibraryMetadata:
    """Update reading progress (chapters read) for a manga in the user's library."""
    updated = await user_service.update_reading_progress(
        current_user.uid, manga_id, body.chapters_read
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Manga not in library")

    return updated


@router.delete("/me/library/{manga_id}", status_code=204)
async def remove_from_library(
    manga_id: str,
    current_user: FirebaseTokenPayload = Depends(get_current_user_verified),
    user_service: UserService = Depends(get_user_service),
) -> None:
    """Remove a manga from the authenticated user's library."""
    removed = await user_service.remove_from_library(current_user.uid, manga_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Manga not in library")
