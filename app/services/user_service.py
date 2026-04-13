"""User service: get-or-create bootstrap by Firebase UID, preferences CRUD."""

import json
import logging
from datetime import datetime, timezone

from app.core.db_adapter import DatabaseAdapter
from app.core.exceptions import PreferencesValidationError
from app.core.firebase_auth import FirebaseTokenPayload
from app.models.user import ReadingPreferences, UpdatePreferencesRequest, UserProfile

_VALID_READER_MODES = frozenset({"vertical", "paged"})
_VALID_LANGUAGES = frozenset({"en", "es", "pt", "fr", "de", "it", "ja", "ko", "zh"})
_VALID_LIBRARY_STATUSES = frozenset({"reading", "completed", "paused"})

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class UserService:
    """Handles local user bootstrap and preferences persistence."""

    def __init__(self, db: DatabaseAdapter) -> None:
        self._db = db

    async def get_or_create_user(self, payload: FirebaseTokenPayload) -> UserProfile:
        """Return the local user row, creating it on first call for a given UID."""
        row = await self._db.fetchone(
            "SELECT firebase_uid, email, display_name, created_at FROM users WHERE firebase_uid = ?",
            payload.uid,
        )

        if row is None:
            now = _utc_now()
            await self._db.execute(
                "INSERT INTO users (firebase_uid, email, display_name, created_at) VALUES (?, ?, ?, ?)",
                payload.uid,
                payload.email,
                payload.display_name,
                now,
            )
            await self._db.commit()
            logger.info("Bootstrapped new local user for Firebase UID %s", payload.uid)
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
            created_at=row["created_at"],
        )

    async def get_preferences(self, firebase_uid: str) -> ReadingPreferences:
        """Return reading preferences, creating defaults on first call."""
        row = await self._db.fetchone(
            "SELECT firebase_uid, default_reader_mode, default_language, updated_at "
            "FROM reading_preferences WHERE firebase_uid = ?",
            firebase_uid,
        )

        if row is None:
            return await self._create_default_preferences(firebase_uid)

        return ReadingPreferences(
            firebase_uid=row["firebase_uid"],
            default_reader_mode=row["default_reader_mode"],
            default_language=row["default_language"],
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

        current = await self.get_preferences(firebase_uid)
        now = _utc_now()

        new_mode = req.default_reader_mode or current.default_reader_mode
        new_lang = req.default_language or current.default_language

        await self._db.execute(
            """INSERT INTO reading_preferences (firebase_uid, default_reader_mode, default_language, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(firebase_uid) DO UPDATE SET
                   default_reader_mode = excluded.default_reader_mode,
                   default_language    = excluded.default_language,
                   updated_at          = excluded.updated_at""",
            firebase_uid,
            new_mode,
            new_lang,
            now,
        )
        await self._db.commit()

        return ReadingPreferences(
            firebase_uid=firebase_uid,
            default_reader_mode=new_mode,
            default_language=new_lang,
            updated_at=now,
        )

    # ── Library ──────────────────────────────────────────────────────────────

    async def get_library_entries(self, firebase_uid: str) -> list[dict]:
        """Return user-library rows with cached manga metadata, newest first."""
        rows = await self._db.fetchall(
            "SELECT manga_id, library_status, added_at, updated_at, title, cover_url, authors "
            "FROM user_library WHERE firebase_uid = ? ORDER BY added_at DESC",
            firebase_uid,
        )
        return [
            {
                "manga_id": row["manga_id"],
                "library_status": row["library_status"],
                "added_at": row["added_at"],
                "updated_at": row["updated_at"],
                "title": row["title"] or "",
                "cover_url": row["cover_url"],
                "authors": json.loads(row["authors"] or "[]"),
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
    ) -> None:
        """Save a manga to the user's library, caching its metadata.

        Uses upsert so that re-adding an existing entry refreshes the cached
        metadata without resetting the library status or added_at timestamp.
        """
        now = _utc_now()
        authors_json = json.dumps(authors or [])
        await self._db.execute(
            "INSERT INTO user_library "
            "(firebase_uid, manga_id, added_at, library_status, updated_at, title, cover_url, authors) "
            "VALUES (?, ?, ?, 'reading', ?, ?, ?, ?) "
            "ON CONFLICT(firebase_uid, manga_id) DO UPDATE SET "
            "title = COALESCE(excluded.title, user_library.title), "
            "cover_url = COALESCE(excluded.cover_url, user_library.cover_url), "
            "authors = COALESCE(excluded.authors, user_library.authors)",
            firebase_uid,
            manga_id,
            now,
            now,
            title,
            cover_url,
            authors_json,
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
            "SELECT manga_id, library_status, added_at, updated_at "
            "FROM user_library WHERE firebase_uid = ? AND manga_id = ?",
            firebase_uid,
            manga_id,
        )

        if row is None:
            return None

        return {
            "manga_id": row["manga_id"],
            "library_status": row["library_status"],
            "added_at": row["added_at"],
            "updated_at": row["updated_at"],
        }

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
        await self._db.execute(
            "INSERT INTO reading_preferences (firebase_uid, default_reader_mode, default_language, updated_at) "
            "VALUES (?, 'vertical', 'en', ?)",
            firebase_uid,
            now,
        )
        await self._db.commit()
        return ReadingPreferences(
            firebase_uid=firebase_uid,
            default_reader_mode="vertical",
            default_language="en",
            updated_at=now,
        )
