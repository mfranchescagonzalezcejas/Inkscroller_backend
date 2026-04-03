"""Users router - authenticated endpoints for profile and reading preferences."""

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user, get_user_service
from app.core.firebase_auth import FirebaseTokenPayload
from app.models.user import ReadingPreferences, UpdatePreferencesRequest, UserProfile
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
