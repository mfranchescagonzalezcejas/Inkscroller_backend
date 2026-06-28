"""Pydantic models for the user profile and reading preferences endpoints."""

from datetime import date
import re

from typing import Literal

from pydantic import BaseModel, field_validator

_USERNAME_PATTERN = re.compile(r"^[a-z0-9_-]{3,30}$")
_MIN_BIRTH_DATE = date(1900, 1, 1)


class UserProfile(BaseModel):
    """Local user profile keyed by Firebase UID."""

    firebase_uid: str
    email: str
    display_name: str | None = None
    username: str | None = None
    birth_date: date | None = None
    created_at: str


class UpdateUserProfileRequest(BaseModel):
    """Payload accepted by `PATCH /users/me` for account profile metadata."""

    username: str | None = None
    birth_date: date | None = None

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        normalized = value.strip().lower()
        if not _USERNAME_PATTERN.fullmatch(normalized):
            raise ValueError(
                "Username must be 3-30 characters and use only letters, numbers, underscores, or hyphens."
            )
        return normalized

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, value: date | None) -> date | None:
        if value is None:
            return None
        if value > date.today():
            raise ValueError("Birth date must not be in the future.")
        if value < _MIN_BIRTH_DATE:
            raise ValueError("Birth date is outside the supported profile range.")
        return value


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


class AddToLibraryRequest(BaseModel):
    """Optional payload accepted by `POST /users/me/library/{manga_id}`.

    Carries manga metadata so the backend can cache it in SQLite and serve
    the library without depending on Jikan at read time.
    All fields are optional for backwards compatibility with older clients.
    """

    title: str | None = None
    cover_url: str | None = None
    authors: list[str] = []
