"""Users router - authenticated endpoints for profile, reading preferences and library."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.age import can_access_content
from app.core.dependencies import (
    get_current_user,
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
    UpdateUserProfileRequest,
    UserProfile,
)
from app.services.manga_service import MangaService
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])

logger = logging.getLogger(__name__)


@router.get("/me", response_model=UserProfile)
async def get_me(
    current_user: FirebaseTokenPayload = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserProfile:
    """Return the local profile for the authenticated Firebase user."""
    # `get_current_user` already bootstraps the user row; here we only need
    # to fetch and return the full profile.
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
    current_user: FirebaseTokenPayload = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> None:
    """Delete the authenticated account and all associated data."""
    await user_service.delete_account(current_user.uid)


@router.get("/me/preferences", response_model=ReadingPreferences)
async def get_preferences(
    current_user: FirebaseTokenPayload = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> ReadingPreferences:
    """Return the reading preferences for the authenticated user."""
    return await user_service.get_preferences(current_user.uid)


@router.put("/me/preferences", response_model=ReadingPreferences)
async def update_preferences(
    body: UpdatePreferencesRequest,
    current_user: FirebaseTokenPayload = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> ReadingPreferences:
    """Update and return the reading preferences for the authenticated user."""
    return await user_service.update_preferences(current_user.uid, body)


# ── Library ───────────────────────────────────────────────────────────────────


@router.get("/me/library", response_model=list[Manga])
async def get_library(
    current_user: FirebaseTokenPayload = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
    user_age: int | None = Depends(get_user_age),
) -> list[Manga]:
    """Return the user's library from cached SQLite data — no Jikan dependency."""
    entries = await user_service.get_library_entries(current_user.uid)
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
            coverUrl=entry["cover_url"],
            authors=entry["authors"],
            library=LibraryMetadata(
                library_status=entry["library_status"],
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
    current_user: FirebaseTokenPayload = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
    manga_service: MangaService = Depends(get_manga_service),
) -> None:
    """Save a manga to the authenticated user's library, caching its metadata."""
    # Fetch manga data to get content_rating
    manga = await manga_service.get_by_id(manga_id, skip_age_filter=True)
    content_rating = manga.get("contentRating") if manga else None

    await user_service.add_to_library(
        current_user.uid,
        manga_id,
        title=body.title,
        cover_url=body.cover_url,
        authors=body.authors,
        content_rating=content_rating,
    )


@router.patch("/me/library/{manga_id}", response_model=LibraryMetadata)
async def update_library_status(
    manga_id: str,
    body: UpdateLibraryStatusRequest,
    current_user: FirebaseTokenPayload = Depends(get_current_user),
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
        added_at=updated["added_at"],
        updated_at=updated["updated_at"],
    )


@router.delete("/me/library/{manga_id}", status_code=204)
async def remove_from_library(
    manga_id: str,
    current_user: FirebaseTokenPayload = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> None:
    """Remove a manga from the authenticated user's library."""
    removed = await user_service.remove_from_library(current_user.uid, manga_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Manga not in library")
