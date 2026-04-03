"""User service: get-or-create bootstrap by Firebase UID, preferences CRUD."""

import logging
from datetime import datetime, timezone

import aiosqlite

from app.core.exceptions import PreferencesValidationError
from app.core.firebase_auth import FirebaseTokenPayload
from app.models.user import ReadingPreferences, UpdatePreferencesRequest, UserProfile

_VALID_READER_MODES = frozenset({"vertical", "paged"})
_VALID_LANGUAGES = frozenset({"en", "es", "pt", "fr", "de", "it", "ja", "ko", "zh"})

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class UserService:
    """Handles local user bootstrap and preferences persistence."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def get_or_create_user(self, payload: FirebaseTokenPayload) -> UserProfile:
        """Return the local user row, creating it on first call for a given UID.

        This is the bootstrap step: the first authenticated request for a
        Firebase UID inserts a new `users` row.
        """
        async with self._db.execute(
            "SELECT firebase_uid, email, display_name, created_at FROM users WHERE firebase_uid = ?",
            (payload.uid,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            now = _utc_now()
            await self._db.execute(
                "INSERT INTO users (firebase_uid, email, display_name, created_at) VALUES (?, ?, ?, ?)",
                (payload.uid, payload.email, payload.display_name, now),
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
        async with self._db.execute(
            "SELECT firebase_uid, default_reader_mode, default_language, updated_at "
            "FROM reading_preferences WHERE firebase_uid = ?",
            (firebase_uid,),
        ) as cursor:
            row = await cursor.fetchone()

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
        """Merge the provided fields into the stored preferences and persist.

        Raises :class:`~app.core.exceptions.PreferencesValidationError` when
        a supplied value is not in the accepted set.
        """
        if req.default_reader_mode is not None and req.default_reader_mode not in _VALID_READER_MODES:
            raise PreferencesValidationError(
                f"Invalid reader mode '{req.default_reader_mode}'. "
                f"Accepted values: {sorted(_VALID_READER_MODES)}."
            )
        if req.default_language is not None and req.default_language not in _VALID_LANGUAGES:
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
            (firebase_uid, new_mode, new_lang, now),
        )
        await self._db.commit()

        return ReadingPreferences(
            firebase_uid=firebase_uid,
            default_reader_mode=new_mode,
            default_language=new_lang,
            updated_at=now,
        )

    async def _create_default_preferences(self, firebase_uid: str) -> ReadingPreferences:
        now = _utc_now()
        await self._db.execute(
            "INSERT INTO reading_preferences (firebase_uid, default_reader_mode, default_language, updated_at) "
            "VALUES (?, 'vertical', 'en', ?)",
            (firebase_uid, now),
        )
        await self._db.commit()
        return ReadingPreferences(
            firebase_uid=firebase_uid,
            default_reader_mode="vertical",
            default_language="en",
            updated_at=now,
        )
