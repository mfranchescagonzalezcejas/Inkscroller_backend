"""Users router - authenticated endpoints for profile, reading preferences and library."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_current_user, get_manga_service, get_user_service
from app.core.firebase_auth import FirebaseTokenPayload
from app.models.manga import Manga
from app.models.user import ReadingPreferences, UpdatePreferencesRequest, UserProfile
from app.services.manga_service import MangaService
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserProfile)
async def get_me(
    current_user: FirebaseTokenPayload = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserProfile:
    """Return the local profile for the authenticated Firebase user."""
    # `get_current_user` already bootstraps the user row; here we only need
    # to fetch and return the full profile.
    return await user_service.get_or_create_user(current_user)


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
    manga_service: MangaService = Depends(get_manga_service),
) -> list[Manga]:
    """Return the full manga objects saved in the authenticated user's library."""
    manga_ids = await user_service.get_library_ids(current_user.uid)
    if not manga_ids:
        return []

    results = await asyncio.gather(
        *[manga_service.get_by_id(mid) for mid in manga_ids],
        return_exceptions=True,
    )

    return [m for m in results if isinstance(m, Manga)]


@router.post("/me/library/{manga_id}", status_code=204)
async def add_to_library(
    manga_id: str,
    current_user: FirebaseTokenPayload = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> None:
    """Save a manga to the authenticated user's library."""
    await user_service.add_to_library(current_user.uid, manga_id)


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
