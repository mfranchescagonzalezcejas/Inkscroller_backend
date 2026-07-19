"""User service: get-or-create bootstrap by Firebase UID, preferences CRUD."""

import asyncio
import json
import logging
import sqlite3
from datetime import UTC, date, datetime

import firebase_admin
from firebase_admin import auth as firebase_auth_sdk

from app.core.db_adapter import DatabaseAdapter, SqliteAdapter
from app.core.exceptions import (
    PreferencesValidationError,
    ProfileConflictError,
    UpstreamServiceError,
)
from app.core.firebase_auth import FirebaseTokenPayload
from app.models.manga import LibraryMetadata
from app.models.user import (
    ReadingPreferences,
    UpdatePreferencesRequest,
    UpdateUserProfileRequest,
    UserProfile,
)

_VALID_READER_MODES = frozenset({"vertical", "paged"})
_VALID_LANGUAGES = frozenset({"en", "es", "pt", "fr", "de", "it", "ja", "ko", "zh"})
_VALID_CONTENT_RATINGS = frozenset({"safe", "suggestive", "all"})
_VALID_LIBRARY_STATUSES = frozenset({"reading", "completed", "paused"})
_VALID_DEMOGRAPHICS = frozenset({"shounen", "shoujo", "seinen", "josei", "unspecified"})

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    """Return the current UTC datetime as an ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def _mask_uid(uid: str) -> str:
    """Return a truncated UID safe for production logs (first 8 chars)."""
    return f"{uid[:8]}..."


def _is_unique_constraint_violation(exc: Exception) -> bool:
    """Check whether the exception represents a SQL unique-constraint violation across DB backends."""
    if isinstance(exc, sqlite3.IntegrityError):
        return "unique" in str(exc).lower()

    sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
    if sqlstate == "23505":
        return True

    return exc.__class__.__name__ == "UniqueViolationError"


def _serialize_birth_date_for_db(
    value: object | None, db: DatabaseAdapter
) -> object | None:
    """Serialize a ``date`` to ISO string for SQLite; pass through for other backends."""
    if isinstance(value, date) and isinstance(db, SqliteAdapter):
        return value.isoformat()
    return value


def _model_field_was_provided(model: UpdateUserProfileRequest, field_name: str) -> bool:
    """Check if a Pydantic v2 model field was explicitly provided (not omitted) in the request."""
    fields_set: set[str] = getattr(model, "model_fields_set", set()) or set()
    if not fields_set:
        fields_set = getattr(model, "__fields_set__", set())
    return field_name in fields_set


class UserService:
    """Handles local user bootstrap and preferences persistence."""

    def __init__(self, db: DatabaseAdapter) -> None:
        """Initialise with a database adapter for local user and preferences storage."""
        self._db = db

    async def get_or_create_user(self, payload: FirebaseTokenPayload) -> UserProfile:
        """Return the local user row, creating it on first call for a given UID."""
        row = await self._db.fetchone(
            "SELECT firebase_uid, email, display_name, username, birth_date, created_at FROM users WHERE firebase_uid = ?",
            payload.uid,
        )

        if row is None:
            now = _utc_now()
            try:
                await self._db.execute(
                    "INSERT INTO users (firebase_uid, email, display_name, created_at) VALUES (?, ?, ?, ?)",
                    payload.uid,
                    payload.email,
                    payload.display_name,
                    now,
                )
                await self._db.commit()
            except Exception as exc:
                if _is_unique_constraint_violation(exc):
                    row = await self._db.fetchone(
                        "SELECT firebase_uid, email, display_name, username, birth_date, created_at "
                        "FROM users WHERE firebase_uid = ?",
                        payload.uid,
                    )
                    if row is None:
                        logger.exception(
                            "Race-condition re-query failed for UID %s",
                            _mask_uid(payload.uid),
                        )
                        raise
                    logger.info(
                        "Raced on bootstrap for UID %s — using existing row",
                        _mask_uid(payload.uid),
                    )
                    await self._db.commit()
                    return UserProfile(
                        firebase_uid=row["firebase_uid"],
                        email=row["email"],
                        display_name=row["display_name"],
                        username=row["username"],
                        birth_date=row["birth_date"],
                        created_at=row["created_at"],
                    )
                logger.exception(
                    "Failed to bootstrap user for UID %s",
                    _mask_uid(payload.uid),
                )
                raise
            logger.info(
                "Bootstrapped new local user for Firebase UID %s",
                _mask_uid(payload.uid),
            )
            return UserProfile(
                firebase_uid=payload.uid,
                email=payload.email,
                display_name=payload.display_name,
                created_at=now,
            )

        return UserProfile(
            firebase_uid=row["firebase_uid"],
            email=row["email"],
            display_name=row["display_name"],
            username=row["username"],
            birth_date=row["birth_date"],
            created_at=row["created_at"],
        )

    async def update_profile_metadata(
        self,
        firebase_uid: str,
        req: UpdateUserProfileRequest | None = None,
        *,
        username: str | None = None,
        birth_date: object | None = None,
    ) -> UserProfile:
        """Update authenticated profile metadata and return the current profile."""
        if req is None:
            update_data: dict[str, object] = {}
            if username is not None:
                update_data["username"] = username
            if birth_date is not None:
                update_data["birth_date"] = birth_date
            profile_update = UpdateUserProfileRequest(**update_data)  # type: ignore[arg-type]
        else:
            profile_update = req
        current = await self._get_user(firebase_uid)

        new_username = (
            profile_update.username
            if _model_field_was_provided(profile_update, "username")
            else current.username
        )
        new_birth_date = (
            profile_update.birth_date
            if _model_field_was_provided(profile_update, "birth_date")
            else current.birth_date
        )

        # Birth date immutability: once set, it cannot be changed.
        # Without this guard, a user could bypass age-gating by editing
        # their birth_date to claim a different age.
        if (
            _model_field_was_provided(profile_update, "birth_date")
            and current.birth_date is not None
            and new_birth_date != current.birth_date
        ):
            # ponytail: generic message — don't reveal whether the field is already set
            raise ProfileConflictError("Profile metadata conflict.")

        if new_username is not None:
            _ = await self._db.fetchone(
                "SELECT firebase_uid FROM users WHERE username = ? AND firebase_uid <> ?",
                new_username,
                firebase_uid,
            )
            # ponytail: no early return on conflict — let the DB constraint fail so
            # the error message is the same regardless of whether the username
            # exists, preventing enumeration.

        birth_date_value = _serialize_birth_date_for_db(new_birth_date, self._db)

        try:
            await self._db.execute(
                "UPDATE users SET username = ?, birth_date = ? WHERE firebase_uid = ?",
                new_username,
                birth_date_value,
                firebase_uid,
            )
            await self._db.commit()
        except Exception as exc:
            if _is_unique_constraint_violation(exc):
                # ponytail: generic message — don't reveal which field conflicted
                raise ProfileConflictError("Profile metadata conflict.") from exc
            raise

        return await self._get_user(firebase_uid)

    async def _get_user(self, firebase_uid: str) -> UserProfile:
        row = await self._db.fetchone(
            "SELECT firebase_uid, email, display_name, username, birth_date, created_at "
            "FROM users WHERE firebase_uid = ?",
            firebase_uid,
        )
        if row is None:
            raise ProfileConflictError("User profile does not exist.")

        return UserProfile(
            firebase_uid=row["firebase_uid"],
            email=row["email"],
            display_name=row["display_name"],
            username=row["username"],
            birth_date=row["birth_date"],
            created_at=row["created_at"],
        )

    # ── Account deletion ───────────────────────────────────────────────────

    async def delete_account(self, firebase_uid: str) -> None:
        """Delete the user's local data and Firebase Auth account.

        Timeouts during Firebase deletion are treated as best-effort: local
        cleanup runs regardless and a pending-deletion record is saved so a
        later reconciliation pass can retry.
        """
        # Reconcile any prior pending deletion for this UID first.
        await self._reconcile_pending_deletion(firebase_uid)
        await self._delete_firebase_user(firebase_uid)
        # Always clean up local data — if Firebase timed out but succeeded
        # remotely, we'd orphan local rows if we skipped cleanup.
        await self._cleanup_local_data(firebase_uid)

    async def _delete_firebase_user(self, firebase_uid: str) -> None:
        """Delete the Firebase Auth user. Skips if SDK not initialized.

        Timeout is treated as a pending/retryable state — the request may have
        succeeded remotely even if the local coroutine timed out. The caller
        must still run local cleanup and flag the pending entry for later
        reconciliation.
        """
        if not firebase_admin._apps:
            logger.info("Firebase Admin not initialized — skipping Auth user deletion.")
            return

        try:
            await asyncio.wait_for(
                asyncio.to_thread(firebase_auth_sdk.delete_user, firebase_uid),
                timeout=10.0,
            )
            logger.info("Deleted Firebase Auth user.")
        except firebase_auth_sdk.UserNotFoundError:
            logger.info("Firebase user already deleted.")
        except TimeoutError:
            # The request may have succeeded on Firebase's side even though
            # we timed out locally — flag so reconciliation can check later.
            logger.warning(
                "Firebase delete_user timed out for %s — marking as pending.",
                _mask_uid(firebase_uid),
            )
            await self._save_pending_deletion(firebase_uid, "timeout")
        except Exception as exc:
            logger.error("Failed to delete Firebase Auth user: %s", exc)
            raise UpstreamServiceError(
                "Firebase Auth", "Firebase Auth deletion failed."
            ) from exc

    async def _cleanup_local_data(self, firebase_uid: str) -> None:
        """Delete local DB rows for the given UID in FK-safe order."""
        await self._db.execute(
            "DELETE FROM user_library WHERE firebase_uid = ?", firebase_uid
        )
        await self._db.execute(
            "DELETE FROM reading_preferences WHERE firebase_uid = ?", firebase_uid
        )
        await self._db.execute("DELETE FROM users WHERE firebase_uid = ?", firebase_uid)
        # Remove any pending-deletion record — if we got here, local cleanup
        # is done (Firebase may have succeeded before or during a timeout).
        await self._db.execute(
            "DELETE FROM user_pending_deletions WHERE firebase_uid = ?", firebase_uid
        )
        await self._db.commit()

    # ── Pending-deletion reconciliation ──────────────────────────────────────

    async def _save_pending_deletion(self, firebase_uid: str, error: str) -> None:
        """Record a pending deletion for later reconciliation."""
        now = _utc_now()
        await self._db.execute(
            "INSERT OR REPLACE INTO user_pending_deletions "
            "(firebase_uid, created_at, retries, last_error) "
            "VALUES (?, ?, COALESCE((SELECT retries FROM user_pending_deletions "
            "WHERE firebase_uid = ?), 0) + 1, ?)",
            firebase_uid,
            now,
            firebase_uid,
            error,
        )
        await self._db.commit()

    async def _reconcile_pending_deletion(self, firebase_uid: str) -> None:
        """Retry Firebase deletion for a UID that timed out previously.

        If the retry succeeds (or the user was already deleted), the pending
        flag is removed so subsequent calls are clean.
        """
        row = await self._db.fetchone(
            "SELECT firebase_uid FROM user_pending_deletions WHERE firebase_uid = ?",
            firebase_uid,
        )
        if row is None:
            return  # nothing to reconcile

        if not firebase_admin._apps:
            logger.info(
                "Firebase Admin not initialized — keeping pending deletion for %s.",
                _mask_uid(firebase_uid),
            )
            return

        try:
            await asyncio.wait_for(
                asyncio.to_thread(firebase_auth_sdk.get_user, firebase_uid),
                timeout=10.0,
            )
            # User still exists — retry the deletion.
            await asyncio.wait_for(
                asyncio.to_thread(firebase_auth_sdk.delete_user, firebase_uid),
                timeout=10.0,
            )
            logger.info(
                "Reconciled pending deletion: deleted Firebase user %s.",
                _mask_uid(firebase_uid),
            )
        except firebase_auth_sdk.UserNotFoundError:
            logger.info(
                "Reconciled pending deletion: user %s already gone.",
                _mask_uid(firebase_uid),
            )
        except (TimeoutError, Exception):
            # Retry failed — keep the pending flag for next time.
            logger.warning(
                "Reconciliation retry failed for %s — will retry on next call.",
                _mask_uid(firebase_uid),
            )
            return

        # Reconciliation succeeded — clear the pending flag.
        await self._db.execute(
            "DELETE FROM user_pending_deletions WHERE firebase_uid = ?",
            firebase_uid,
        )
        await self._db.commit()

    async def process_all_pending_deletions(self) -> None:
        """Retry Firebase deletion for every pending entry.

        Call this at application startup so unresolved timeouts from a previous
        run are reconciled.
        """
        rows = await self._db.fetchall(
            "SELECT firebase_uid FROM user_pending_deletions"
        )
        for row in rows:
            await self._reconcile_pending_deletion(row["firebase_uid"])

    async def get_preferences(self, firebase_uid: str) -> ReadingPreferences:
        """Return reading preferences, creating defaults on first call."""
        row = await self._db.fetchone(
            "SELECT firebase_uid, default_reader_mode, default_language, content_rating_filter, demographic_filter, updated_at "
            "FROM reading_preferences WHERE firebase_uid = ?",
            firebase_uid,
        )

        if row is None:
            return await self._create_default_preferences(firebase_uid)

        demographic = (
            json.loads(row["demographic_filter"]) if row["demographic_filter"] else None
        )
        return ReadingPreferences(
            firebase_uid=row["firebase_uid"],
            default_reader_mode=row["default_reader_mode"],
            default_language=row["default_language"],
            content_rating_filter=row["content_rating_filter"],
            demographic_filter=demographic,
            updated_at=row["updated_at"],
        )

    async def update_preferences(
        self, firebase_uid: str, req: UpdatePreferencesRequest
    ) -> ReadingPreferences:
        """Merge the provided fields into the stored preferences and persist."""
        if (
            req.default_reader_mode is not None
            and req.default_reader_mode not in _VALID_READER_MODES
        ):
            raise PreferencesValidationError(
                f"Invalid reader mode '{req.default_reader_mode}'. "
                f"Accepted values: {sorted(_VALID_READER_MODES)}."
            )
        if (
            req.default_language is not None
            and req.default_language not in _VALID_LANGUAGES
        ):
            raise PreferencesValidationError(
                f"Invalid language '{req.default_language}'. "
                f"Accepted values: {sorted(_VALID_LANGUAGES)}."
            )
        if (
            req.content_rating_filter is not None
            and req.content_rating_filter not in _VALID_CONTENT_RATINGS
        ):
            raise PreferencesValidationError(
                f"Invalid content rating filter '{req.content_rating_filter}'. "
                f"Accepted values: {sorted(_VALID_CONTENT_RATINGS)}."
            )

        if req.demographic_filter is not None:
            invalid = [
                d for d in req.demographic_filter if d not in _VALID_DEMOGRAPHICS
            ]
            if invalid:
                raise PreferencesValidationError(
                    f"Invalid demographic values: {invalid}. "
                    f"Accepted values: {sorted(_VALID_DEMOGRAPHICS)}."
                )

        current = await self.get_preferences(firebase_uid)
        now = _utc_now()

        new_mode = req.default_reader_mode or current.default_reader_mode
        new_lang = req.default_language or current.default_language
        new_filter = (
            req.content_rating_filter
            if req.content_rating_filter is not None
            else current.content_rating_filter
        )
        # ponytail: model_fields_set distinguishes "sent as null" from "omitted"
        new_demographic = (
            req.demographic_filter
            if "demographic_filter" in req.model_fields_set
            else current.demographic_filter
        )
        demographic_json = (
            json.dumps(new_demographic) if new_demographic is not None else None
        )

        await self._db.execute(
            """INSERT INTO reading_preferences
                   (firebase_uid, default_reader_mode, default_language, content_rating_filter, demographic_filter, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(firebase_uid) DO UPDATE SET
                   default_reader_mode     = excluded.default_reader_mode,
                   default_language        = excluded.default_language,
                   content_rating_filter   = excluded.content_rating_filter,
                   demographic_filter      = excluded.demographic_filter,
                   updated_at              = excluded.updated_at""",
            firebase_uid,
            new_mode,
            new_lang,
            new_filter,
            demographic_json,
            now,
        )
        await self._db.commit()

        return ReadingPreferences(
            firebase_uid=firebase_uid,
            default_reader_mode=new_mode,
            default_language=new_lang,
            content_rating_filter=new_filter,
            demographic_filter=new_demographic,
            updated_at=now,
        )

    # ── Library ──────────────────────────────────────────────────────────────

    async def get_library_entries(self, firebase_uid: str) -> list[dict]:
        """Return user-library rows with cached manga metadata, newest first."""
        rows = await self._db.fetchall(
            "SELECT manga_id, library_status, chapters_read, added_at, updated_at, title, cover_url, "
            "authors, content_rating, description, demographic, status, score, rank, popularity, "
            "members, favorites, serialization, genres, chapters, start_year, end_year, mal_id, "
            "manga_type "
            "FROM user_library WHERE firebase_uid = ? ORDER BY added_at DESC",
            firebase_uid,
        )
        return [
            {
                "manga_id": row["manga_id"],
                "library_status": row["library_status"],
                "chapters_read": row["chapters_read"],
                "added_at": row["added_at"],
                "updated_at": row["updated_at"],
                "title": row["title"] or "",
                "cover_url": row["cover_url"],
                "authors": json.loads(row["authors"] or "[]"),
                "content_rating": row.get("content_rating"),
                "description": row["description"],
                "demographic": row["demographic"],
                "status": row["status"],
                "score": row["score"],
                "rank": row["rank"],
                "popularity": row["popularity"],
                "members": row["members"],
                "favorites": row["favorites"],
                "serialization": row["serialization"],
                "genres": json.loads(row["genres"] or "[]"),
                "chapters": row["chapters"],
                "start_year": row["start_year"],
                "end_year": row["end_year"],
                "mal_id": row["mal_id"],
                "manga_type": row.get("manga_type"),
            }
            for row in rows
        ]

    async def get_library_ids(self, firebase_uid: str) -> list[str]:
        """Return the manga IDs saved in the user's library, newest first."""
        entries = await self.get_library_entries(firebase_uid)
        return [entry["manga_id"] for entry in entries]

    async def add_to_library(
        self,
        firebase_uid: str,
        manga_id: str,
        title: str | None = None,
        cover_url: str | None = None,
        authors: list[str] | None = None,
        content_rating: str | None = None,
        description: str | None = None,
        demographic: str | None = None,
        status: str | None = None,
        score: float | None = None,
        rank: int | None = None,
        popularity: int | None = None,
        members: int | None = None,
        favorites: int | None = None,
        serialization: str | None = None,
        genres: list[str] | None = None,
        chapters: int | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
        mal_id: int | None = None,
        manga_type: str | None = None,
    ) -> None:
        """Save a manga to the user's library, caching its metadata.

        Uses upsert so that re-adding an existing entry refreshes the cached
        metadata without resetting the library status or added_at timestamp.
        """
        now = _utc_now()
        # ponytail: pass None for empty/missing collections so COALESCE
        # in ON CONFLICT preserves stored data when re-adding with no data.
        authors_json = json.dumps(authors) if authors else None
        genres_json = json.dumps(genres) if genres else None
        await self._db.execute(
            "INSERT INTO user_library "
            "(firebase_uid, manga_id, added_at, library_status, updated_at, title, cover_url, "
            "authors, chapters_read, content_rating, description, demographic, status, score, "
            "rank, popularity, members, favorites, serialization, genres, chapters, "
            "start_year, end_year, mal_id, manga_type) "
            "VALUES (?, ?, ?, 'reading', ?, ?, ?, COALESCE(?, '[]'), ?, ?, ?, ?, ?, ?, "
            "?, ?, ?, ?, ?, COALESCE(?, '[]'), ?, ?, ?, ?, ?) "
            "ON CONFLICT(firebase_uid, manga_id) DO UPDATE SET "
            "title = COALESCE(excluded.title, user_library.title), "
            "cover_url = COALESCE(excluded.cover_url, user_library.cover_url), "
            "authors = COALESCE(excluded.authors, user_library.authors), "
            "content_rating = COALESCE(excluded.content_rating, user_library.content_rating), "
            "description = COALESCE(excluded.description, user_library.description), "
            "demographic = COALESCE(excluded.demographic, user_library.demographic), "
            "status = COALESCE(excluded.status, user_library.status), "
            "score = COALESCE(excluded.score, user_library.score), "
            "rank = COALESCE(excluded.rank, user_library.rank), "
            "popularity = COALESCE(excluded.popularity, user_library.popularity), "
            "members = COALESCE(excluded.members, user_library.members), "
            "favorites = COALESCE(excluded.favorites, user_library.favorites), "
            "serialization = COALESCE(excluded.serialization, user_library.serialization), "
            "genres = COALESCE(excluded.genres, user_library.genres), "
            "chapters = COALESCE(excluded.chapters, user_library.chapters), "
            "start_year = COALESCE(excluded.start_year, user_library.start_year), "
            "end_year = COALESCE(excluded.end_year, user_library.end_year), "
            "mal_id = COALESCE(excluded.mal_id, user_library.mal_id), "
            "manga_type = COALESCE(excluded.manga_type, user_library.manga_type)",
            firebase_uid,
            manga_id,
            now,
            now,
            title,
            cover_url,
            authors_json,
            0,
            content_rating,
            description,
            demographic,
            status,
            score,
            rank,
            popularity,
            members,
            favorites,
            serialization,
            genres_json,
            chapters,
            start_year,
            end_year,
            mal_id,
            manga_type,
        )
        await self._db.commit()

    async def update_library_status(
        self, firebase_uid: str, manga_id: str, library_status: str
    ) -> dict[str, str] | None:
        """Update status and ``updated_at`` for a library row; returns row if found."""
        if library_status not in _VALID_LIBRARY_STATUSES:
            return None

        now = _utc_now()
        rowcount = await self._db.execute(
            "UPDATE user_library SET library_status = ?, updated_at = ? "
            "WHERE firebase_uid = ? AND manga_id = ?",
            library_status,
            now,
            firebase_uid,
            manga_id,
        )
        await self._db.commit()

        if rowcount == 0:
            return None

        row = await self._db.fetchone(
            "SELECT manga_id, library_status, chapters_read, added_at, updated_at "
            "FROM user_library WHERE firebase_uid = ? AND manga_id = ?",
            firebase_uid,
            manga_id,
        )

        if row is None:
            return None

        return {
            "manga_id": row["manga_id"],
            "library_status": row["library_status"],
            "chapters_read": row["chapters_read"],
            "added_at": row["added_at"],
            "updated_at": row["updated_at"],
        }

    async def update_reading_progress(
        self, firebase_uid: str, manga_id: str, chapters_read: int
    ) -> LibraryMetadata | None:
        """Update ``chapters_read`` for a manga in the user's library.

        Returns the updated metadata, or ``None`` if the manga is not in the library.
        """
        now = _utc_now()
        rowcount = await self._db.execute(
            "UPDATE user_library SET chapters_read = ?, updated_at = ? "
            "WHERE firebase_uid = ? AND manga_id = ?",
            chapters_read,
            now,
            firebase_uid,
            manga_id,
        )
        await self._db.commit()

        if rowcount == 0:
            return None

        row = await self._db.fetchone(
            "SELECT manga_id, library_status, chapters_read, added_at, updated_at "
            "FROM user_library WHERE firebase_uid = ? AND manga_id = ?",
            firebase_uid,
            manga_id,
        )
        if row is None:
            return None

        return LibraryMetadata(
            library_status=row["library_status"],
            chapters_read=row["chapters_read"],
            added_at=row["added_at"],
            updated_at=row["updated_at"],
        )

    async def remove_from_library(self, firebase_uid: str, manga_id: str) -> bool:
        """Remove a manga from the user's library. Returns True if it existed."""
        rowcount = await self._db.execute(
            "DELETE FROM user_library WHERE firebase_uid = ? AND manga_id = ?",
            firebase_uid,
            manga_id,
        )
        await self._db.commit()
        return rowcount > 0

    async def _create_default_preferences(
        self, firebase_uid: str
    ) -> ReadingPreferences:
        now = _utc_now()
        try:
            await self._db.execute(
                "INSERT INTO reading_preferences (firebase_uid, default_reader_mode, default_language, content_rating_filter, demographic_filter, updated_at) "
                "VALUES (?, 'vertical', 'en', NULL, NULL, ?)",
                firebase_uid,
                now,
            )
            await self._db.commit()
        except Exception as exc:
            if _is_unique_constraint_violation(exc):
                row = await self._db.fetchone(
                    "SELECT firebase_uid, default_reader_mode, default_language, content_rating_filter, demographic_filter, updated_at "
                    "FROM reading_preferences WHERE firebase_uid = ?",
                    firebase_uid,
                )
                if row is not None:
                    demographic = (
                        json.loads(row["demographic_filter"])
                        if row["demographic_filter"]
                        else None
                    )
                    await self._db.commit()
                    return ReadingPreferences(
                        firebase_uid=row["firebase_uid"],
                        default_reader_mode=row["default_reader_mode"],
                        default_language=row["default_language"],
                        content_rating_filter=row["content_rating_filter"],
                        demographic_filter=demographic,
                        updated_at=row["updated_at"],
                    )
                logger.exception(
                    "Race-condition re-query for preferences failed for UID %s",
                    _mask_uid(firebase_uid),
                )
                raise
            logger.exception(
                "Failed to create default preferences for UID %s",
                _mask_uid(firebase_uid),
            )
            raise
        return ReadingPreferences(
            firebase_uid=firebase_uid,
            default_reader_mode="vertical",
            default_language="en",
            content_rating_filter=None,
            demographic_filter=None,
            updated_at=now,
        )
