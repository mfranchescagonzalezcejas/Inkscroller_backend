"""Pydantic models for the user profile and reading preferences endpoints."""

from typing import Literal

from pydantic import BaseModel


class UserProfile(BaseModel):
    """Local user profile keyed by Firebase UID."""

    firebase_uid: str
    email: str
    display_name: str | None = None
    created_at: str


class ReadingPreferences(BaseModel):
    """Reading preferences for the authenticated user."""

    firebase_uid: str
    default_reader_mode: str = "vertical"
    default_language: str = "en"
    updated_at: str


class UpdatePreferencesRequest(BaseModel):
    """Payload accepted by `PUT /users/me/preferences`."""

    default_reader_mode: str | None = None
    default_language: str | None = None


class UpdateLibraryStatusRequest(BaseModel):
    """Payload accepted by `PATCH /users/me/library/{manga_id}`."""

    library_status: Literal["reading", "completed", "paused"]
