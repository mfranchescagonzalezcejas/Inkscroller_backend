"""Tests for Firebase-auth user/preferences/library endpoints.

Strategy:
- `get_current_user` dependency is overridden with a fake that returns a
  `FirebaseTokenPayload` directly, so no real Firebase Admin SDK call is made.
- An in-memory SQLite database is used via a `get_db` override so tests are
  hermetic and fast.
- `init_db(":memory:")` is used so the schema is always in sync with production
  DDL — no hardcoded table definitions in tests.
- Tests cover: valid token flow, missing/invalid token rejection, first-request
  bootstrap, default preferences, preference update persistence, and the full
  library add/list/remove lifecycle.
"""

import asyncio
import os
import sqlite3
import tempfile
import unittest
from datetime import date
from importlib.util import find_spec
from unittest.mock import AsyncMock, patch

if find_spec("fastapi") is None or find_spec("dotenv") is None:
    raise unittest.SkipTest("fastapi/python-dotenv not installed")

from fastapi.testclient import TestClient

from app.core.database import init_db
from app.core.db_adapter import DatabaseAdapter
from app.core.dependencies import get_current_user, get_db, get_manga_service, get_user_age
from app.core.exceptions import ProfileConflictError
from app.core.firebase_auth import FirebaseTokenPayload
from firebase_admin import auth as firebase_auth_sdk
from app.services.user_service import UserService
from tests.api.helpers import create_hermetic_test_app

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_FAKE_PAYLOAD = FirebaseTokenPayload(
    uid="test-uid-001",
    email="user@example.com",
    display_name="Test User",
)

_FAKE_MANGA = {
    "id": "manga-abc-123",
    "title": "Test Manga",
    "description": "A test manga",
    "coverUrl": None,
    "contentRating": None,
}

_FAKE_MANGA_EROTICA = {
    "id": "manga-erotica-001",
    "title": "Erotica Manga",
    "description": "Age-restricted manga",
    "coverUrl": None,
    "contentRating": "erotica",
}

_FAKE_MANGA_SUGGESTIVE = {
    "id": "manga-suggestive-001",
    "title": "Suggestive Manga",
    "description": "Suggestive manga",
    "coverUrl": None,
    "contentRating": "suggestive",
}


async def _make_test_db() -> DatabaseAdapter:
    """Create an in-memory SQLite DB using the real production DDL via init_db."""
    return await init_db(":memory:")


class UsersEndpointTests(unittest.TestCase):
    """Authenticated /users/me and /users/me/preferences endpoint tests."""

    def setUp(self):
        self.app = create_hermetic_test_app()
        self.db = asyncio.run(_make_test_db())
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_user] = self._fake_auth

    def tearDown(self):
        self.app.dependency_overrides.clear()
        asyncio.run(self.db.close())

    @staticmethod
    async def _fake_auth() -> FirebaseTokenPayload:
        return _FAKE_PAYLOAD

    # -- GET /users/me --------------------------------------------------------

    def test_get_me_bootstraps_user_on_first_request(self):
        with TestClient(self.app) as client:
            response = client.get(
                "/users/me",
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["firebase_uid"], _FAKE_PAYLOAD.uid)
        self.assertEqual(data["email"], _FAKE_PAYLOAD.email)
        self.assertIsNone(data["username"])
        self.assertIsNone(data["birth_date"])

    def test_get_me_returns_same_user_on_second_request(self):
        with TestClient(self.app) as client:
            client.get("/users/me", headers={"Authorization": "Bearer fake-token"})
            response = client.get(
                "/users/me",
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["firebase_uid"], _FAKE_PAYLOAD.uid)

    # -- PATCH /users/me ------------------------------------------------------

    def test_patch_me_updates_username_and_birth_date(self):
        with TestClient(self.app) as client:
            response = client.patch(
                "/users/me",
                json={"username": "Reader_16", "birth_date": "2008-06-15"},
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["username"], "reader_16")
        self.assertEqual(data["birth_date"], "2008-06-15")
        self.assertEqual(data["firebase_uid"], _FAKE_PAYLOAD.uid)

    def test_patch_me_subsequent_get_returns_profile_metadata(self):
        with TestClient(self.app) as client:
            client.patch(
                "/users/me",
                json={"username": "reader-two", "birth_date": "2001-01-20"},
                headers={"Authorization": "Bearer fake-token"},
            )
            response = client.get(
                "/users/me",
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["username"], "reader-two")
        self.assertEqual(data["birth_date"], "2001-01-20")

    def test_patch_me_empty_payload_preserves_profile_metadata(self):
        with TestClient(self.app) as client:
            client.patch(
                "/users/me",
                json={"username": "reader-three", "birth_date": "2001-01-20"},
                headers={"Authorization": "Bearer fake-token"},
            )
            response = client.patch(
                "/users/me",
                json={},
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["username"], "reader-three")
        self.assertEqual(data["birth_date"], "2001-01-20")

    def test_patch_me_null_username_clears_only_username(self):
        with TestClient(self.app) as client:
            client.patch(
                "/users/me",
                json={"username": "reader-four", "birth_date": "2001-01-20"},
                headers={"Authorization": "Bearer fake-token"},
            )
            response = client.patch(
                "/users/me",
                json={"username": None},
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data["username"])
        self.assertEqual(data["birth_date"], "2001-01-20")

    def test_patch_me_rejects_birth_date_change_after_initial_set(self):
        """Birth date is immutable once set — changing it should return 409."""
        with TestClient(self.app) as client:
            client.patch(
                "/users/me",
                json={"username": "reader-five", "birth_date": "2001-01-20"},
                headers={"Authorization": "Bearer fake-token"},
            )
            response = client.patch(
                "/users/me",
                json={"birth_date": "1990-06-15"},
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 409)
        data = response.json()
        self.assertEqual(data["error"], "profile_conflict")

    def test_patch_me_rejects_birth_date_clear_after_initial_set(self):
        """Clearing birth_date to None after it was set should return 409."""
        with TestClient(self.app) as client:
            client.patch(
                "/users/me",
                json={"username": "reader-six", "birth_date": "2001-01-20"},
                headers={"Authorization": "Bearer fake-token"},
            )
            response = client.patch(
                "/users/me",
                json={"birth_date": None},
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 409)
        data = response.json()
        self.assertEqual(data["error"], "profile_conflict")

    def test_patch_me_same_birth_date_is_idempotent(self):
        """Setting the same birth_date value again should still work."""
        with TestClient(self.app) as client:
            client.patch(
                "/users/me",
                json={"username": "reader-seven", "birth_date": "2001-01-20"},
                headers={"Authorization": "Bearer fake-token"},
            )
            response = client.patch(
                "/users/me",
                json={"birth_date": "2001-01-20"},
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["birth_date"], "2001-01-20")

    def test_patch_me_rejects_invalid_username(self):
        with TestClient(self.app) as client:
            response = client.patch(
                "/users/me",
                json={"username": "no spaces", "birth_date": "2001-01-20"},
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 422)

    def test_patch_me_rejects_future_birth_date(self):
        with TestClient(self.app) as client:
            response = client.patch(
                "/users/me",
                json={"username": "reader_future", "birth_date": "2999-01-01"},
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 422)

    def test_patch_me_rejects_duplicate_username(self):
        other_payload = FirebaseTokenPayload(
            uid="test-uid-002",
            email="other@example.com",
            display_name="Other User",
        )
        asyncio.run(UserService(self.db).get_or_create_user(other_payload))

        with TestClient(self.app) as client:
            client.patch(
                "/users/me",
                json={"username": "taken-name", "birth_date": "2001-01-20"},
                headers={"Authorization": "Bearer fake-token"},
            )

        self.app.dependency_overrides[get_current_user] = lambda: other_payload

        with TestClient(self.app) as client:
            response = client.patch(
                "/users/me",
                json={"username": "taken-name", "birth_date": "2002-02-21"},
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 409)

    def test_existing_sqlite_users_schema_migrates_profile_metadata(self):
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            conn = sqlite3.connect(db_path)
            conn.execute(
                """CREATE TABLE users (
                    firebase_uid TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    display_name TEXT,
                    created_at TEXT NOT NULL
                )"""
            )
            conn.execute(
                """CREATE TABLE reading_preferences (
                    firebase_uid TEXT PRIMARY KEY REFERENCES users(firebase_uid),
                    default_reader_mode TEXT NOT NULL DEFAULT 'vertical',
                    default_language TEXT NOT NULL DEFAULT 'en',
                    updated_at TEXT NOT NULL
                )"""
            )
            conn.execute(
                """CREATE TABLE user_library (
                    firebase_uid TEXT NOT NULL REFERENCES users(firebase_uid),
                    manga_id TEXT NOT NULL,
                    added_at TEXT NOT NULL,
                    PRIMARY KEY (firebase_uid, manga_id)
                )"""
            )
            conn.commit()
            conn.close()

            migrated_db = asyncio.run(init_db(db_path))
            try:
                profile = asyncio.run(
                    UserService(migrated_db).get_or_create_user(_FAKE_PAYLOAD)
                )
                asyncio.run(
                    UserService(migrated_db).update_profile_metadata(
                        profile.firebase_uid,
                        username="migrated_reader",
                        birth_date="2000-01-01",
                    )
                )
                index_row = asyncio.run(
                    migrated_db.fetchone(
                        "SELECT name FROM sqlite_master WHERE type = ? AND name = ?",
                        "index",
                        "idx_users_username_unique",
                    )
                )
            finally:
                asyncio.run(migrated_db.close())

            self.assertEqual(profile.firebase_uid, _FAKE_PAYLOAD.uid)
            self.assertIsNotNone(index_row)
        finally:
            os.remove(db_path)

    def test_profile_update_maps_db_unique_constraint_to_conflict(self):
        class RaceConflictDb(DatabaseAdapter):
            async def execute(self, query, *args):
                if query.startswith("UPDATE users SET username"):
                    raise sqlite3.IntegrityError(
                        "UNIQUE constraint failed: users.username"
                    )
                return 1

            async def fetchone(self, query, *args):
                if "WHERE firebase_uid = ?" in query:
                    return {
                        "firebase_uid": _FAKE_PAYLOAD.uid,
                        "email": _FAKE_PAYLOAD.email,
                        "display_name": _FAKE_PAYLOAD.display_name,
                        "username": None,
                        "birth_date": None,
                        "created_at": "2026-01-01T00:00:00+00:00",
                    }
                return None

            async def fetchall(self, query, *args):
                return []

            async def commit(self):
                return None

            async def close(self):
                return None

        with self.assertRaises(ProfileConflictError):
            asyncio.run(
                UserService(RaceConflictDb()).update_profile_metadata(
                    _FAKE_PAYLOAD.uid,
                    username="raced_reader",
                    birth_date="2000-01-01",
                )
            )

    def test_profile_update_maps_postgres_unique_constraint_to_conflict(self):
        class UniqueViolationError(Exception):
            sqlstate = "23505"

        class PostgresRaceConflictDb(DatabaseAdapter):
            async def execute(self, query, *args):
                if query.startswith("UPDATE users SET username"):
                    raise UniqueViolationError(
                        "duplicate key value violates unique constraint"
                    )
                return 1

            async def fetchone(self, query, *args):
                if "WHERE firebase_uid = ?" in query:
                    return {
                        "firebase_uid": _FAKE_PAYLOAD.uid,
                        "email": _FAKE_PAYLOAD.email,
                        "display_name": _FAKE_PAYLOAD.display_name,
                        "username": None,
                        "birth_date": None,
                        "created_at": "2026-01-01T00:00:00+00:00",
                    }
                return None

            async def fetchall(self, query, *args):
                return []

            async def commit(self):
                return None

            async def close(self):
                return None

        with self.assertRaises(ProfileConflictError):
            asyncio.run(
                UserService(PostgresRaceConflictDb()).update_profile_metadata(
                    _FAKE_PAYLOAD.uid,
                    username="raced_reader",
                    birth_date=date(2000, 1, 1),
                )
            )

    def test_profile_update_keeps_birth_date_as_date_for_postgres_adapters(self):
        class CapturingPostgresDb(DatabaseAdapter):
            def __init__(self):
                self.birth_date_value = None

            async def execute(self, query, *args):
                if query.startswith("UPDATE users SET username"):
                    self.birth_date_value = args[1]
                return 1

            async def fetchone(self, query, *args):
                if "WHERE firebase_uid = ?" in query:
                    return {
                        "firebase_uid": _FAKE_PAYLOAD.uid,
                        "email": _FAKE_PAYLOAD.email,
                        "display_name": _FAKE_PAYLOAD.display_name,
                        "username": None,
                        "birth_date": None,
                        "created_at": "2026-01-01T00:00:00+00:00",
                    }
                return None

            async def fetchall(self, query, *args):
                return []

            async def commit(self):
                return None

            async def close(self):
                return None

        db = CapturingPostgresDb()

        asyncio.run(
            UserService(db).update_profile_metadata(
                _FAKE_PAYLOAD.uid,
                username="postgres_reader",
                birth_date=date(2000, 1, 1),
            )
        )

        self.assertEqual(db.birth_date_value, date(2000, 1, 1))

    # -- GET /users/me/preferences --------------------------------------------

    def test_get_preferences_returns_defaults_on_first_request(self):
        asyncio.run(UserService(self.db).get_or_create_user(_FAKE_PAYLOAD))

        with TestClient(self.app) as client:
            response = client.get(
                "/users/me/preferences",
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["default_reader_mode"], "vertical")
        self.assertEqual(data["default_language"], "en")

    # -- PUT /users/me/preferences --------------------------------------------

    def test_update_preferences_persists_and_returns_updated_values(self):
        asyncio.run(UserService(self.db).get_or_create_user(_FAKE_PAYLOAD))

        with TestClient(self.app) as client:
            response = client.put(
                "/users/me/preferences",
                json={"default_reader_mode": "paged", "default_language": "es"},
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["default_reader_mode"], "paged")
        self.assertEqual(data["default_language"], "es")

    def test_update_preferences_subsequent_get_returns_updated_values(self):
        asyncio.run(UserService(self.db).get_or_create_user(_FAKE_PAYLOAD))

        with TestClient(self.app) as client:
            client.put(
                "/users/me/preferences",
                json={"default_reader_mode": "paged"},
                headers={"Authorization": "Bearer fake-token"},
            )
            response = client.get(
                "/users/me/preferences",
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["default_reader_mode"], "paged")

    # -- Auth rejection -------------------------------------------------------

    def test_missing_token_returns_401(self):
        self.app.dependency_overrides.pop(get_current_user, None)

        with TestClient(self.app) as client:
            response = client.get("/users/me")

        self.assertEqual(response.status_code, 401)

    def test_invalid_token_returns_401(self):
        self.app.dependency_overrides.pop(get_current_user, None)

        with TestClient(self.app) as client:
            response = client.get(
                "/users/me",
                headers={"Authorization": "Bearer not-a-real-token"},
            )

        self.assertEqual(response.status_code, 401)


class LibraryEndpointTests(unittest.TestCase):
    """Authenticated /users/me/library endpoint tests."""

    def setUp(self):
        self.app = create_hermetic_test_app()
        self.db = asyncio.run(_make_test_db())
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_user] = self._fake_auth

        # Bootstrap user row required by FK constraint.
        asyncio.run(UserService(self.db).get_or_create_user(_FAKE_PAYLOAD))

        # Fake MangaService that returns _FAKE_MANGA for any ID.
        fake_manga_service = AsyncMock()
        fake_manga_service.get_by_id = AsyncMock(return_value=_FAKE_MANGA)
        self.app.dependency_overrides[get_manga_service] = lambda: fake_manga_service

    def tearDown(self):
        self.app.dependency_overrides.clear()
        asyncio.run(self.db.close())

    @staticmethod
    async def _fake_auth() -> FirebaseTokenPayload:
        return _FAKE_PAYLOAD

    def assert_response_key_absent(self, value: object, forbidden_key: str) -> None:
        if isinstance(value, dict):
            self.assertNotIn(forbidden_key, value)
            for nested in value.values():
                self.assert_response_key_absent(nested, forbidden_key)
        elif isinstance(value, list):
            for nested in value:
                self.assert_response_key_absent(nested, forbidden_key)

    # -- GET /users/me/library ------------------------------------------------

    def test_get_library_empty_on_new_user(self):
        with TestClient(self.app) as client:
            response = client.get(
                "/users/me/library",
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_library_returns_manga_after_add(self):
        asyncio.run(
            UserService(self.db).update_profile_metadata(
                _FAKE_PAYLOAD.uid,
                username="private_reader",
                birth_date="2000-05-10",
            )
        )

        with TestClient(self.app) as client:
            client.post(
                "/users/me/library/manga-abc-123",
                headers={"Authorization": "Bearer fake-token"},
            )
            response = client.get(
                "/users/me/library",
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], _FAKE_MANGA["id"])
        self.assertIn("library", data[0])
        self.assert_response_key_absent(data[0], "username")
        self.assert_response_key_absent(data[0], "birth_date")
        self.assertEqual(data[0]["library"]["library_status"], "reading")
        self.assertIn("added_at", data[0]["library"])
        self.assertIn("updated_at", data[0]["library"])

    # -- POST /users/me/library/{manga_id} ------------------------------------

    def test_add_to_library_returns_204(self):
        with TestClient(self.app) as client:
            response = client.post(
                "/users/me/library/manga-abc-123",
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 204)

    def test_add_same_manga_twice_is_idempotent(self):
        with TestClient(self.app) as client:
            client.post(
                "/users/me/library/manga-abc-123",
                headers={"Authorization": "Bearer fake-token"},
            )
            response = client.post(
                "/users/me/library/manga-abc-123",
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 204)

    # -- PATCH /users/me/library/{manga_id} -----------------------------------

    def test_patch_library_status_returns_200_and_metadata(self):
        with TestClient(self.app) as client:
            client.post(
                "/users/me/library/manga-abc-123",
                headers={"Authorization": "Bearer fake-token"},
            )
            response = client.patch(
                "/users/me/library/manga-abc-123",
                json={"library_status": "completed"},
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["library_status"], "completed")
        self.assertIn("added_at", data)
        self.assertIn("updated_at", data)

    def test_patch_library_status_reflected_in_get_library(self):
        with TestClient(self.app) as client:
            client.post(
                "/users/me/library/manga-abc-123",
                headers={"Authorization": "Bearer fake-token"},
            )
            client.patch(
                "/users/me/library/manga-abc-123",
                json={"library_status": "paused"},
                headers={"Authorization": "Bearer fake-token"},
            )
            response = client.get(
                "/users/me/library",
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data[0]["library"]["library_status"], "paused")

    def test_patch_nonexistent_library_item_returns_404(self):
        with TestClient(self.app) as client:
            response = client.patch(
                "/users/me/library/does-not-exist",
                json={"library_status": "completed"},
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 404)

    def test_patch_library_status_invalid_value_returns_422(self):
        with TestClient(self.app) as client:
            client.post(
                "/users/me/library/manga-abc-123",
                headers={"Authorization": "Bearer fake-token"},
            )
            response = client.patch(
                "/users/me/library/manga-abc-123",
                json={"library_status": "dropped"},
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 422)

    # -- DELETE /users/me/library/{manga_id} ----------------------------------

    def test_remove_from_library_returns_204(self):
        with TestClient(self.app) as client:
            client.post(
                "/users/me/library/manga-abc-123",
                headers={"Authorization": "Bearer fake-token"},
            )
            response = client.delete(
                "/users/me/library/manga-abc-123",
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 204)

    def test_remove_from_library_then_get_returns_empty(self):
        with TestClient(self.app) as client:
            client.post(
                "/users/me/library/manga-abc-123",
                headers={"Authorization": "Bearer fake-token"},
            )
            client.delete(
                "/users/me/library/manga-abc-123",
                headers={"Authorization": "Bearer fake-token"},
            )
            response = client.get(
                "/users/me/library",
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_remove_nonexistent_returns_404(self):
        with TestClient(self.app) as client:
            response = client.delete(
                "/users/me/library/does-not-exist",
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 404)

    # -- Library content_rating storage ---------------------------------------

    def test_add_to_library_stores_content_rating(self):
        """add_to_library should fetch and store content_rating from MangaService."""
        fake_manga_service = AsyncMock()
        fake_manga_service.get_by_id = AsyncMock(return_value=_FAKE_MANGA_EROTICA)
        self.app.dependency_overrides[get_manga_service] = lambda: fake_manga_service

        with TestClient(self.app) as client:
            client.post(
                "/users/me/library/manga-erotica-001",
                headers={"Authorization": "Bearer fake-token"},
            )

        # Verify content_rating is stored in DB
        row = asyncio.run(
            self.db.fetchone(
                "SELECT content_rating FROM user_library WHERE manga_id = ?",
                "manga-erotica-001",
            )
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["content_rating"], "erotica")

    def test_add_to_library_passes_content_rating_to_service(self):
        """add_to_library route should pass content_rating to UserService."""
        fake_manga_service = AsyncMock()
        fake_manga_service.get_by_id = AsyncMock(return_value=_FAKE_MANGA_SUGGESTIVE)
        self.app.dependency_overrides[get_manga_service] = lambda: fake_manga_service

        with TestClient(self.app) as client:
            client.post(
                "/users/me/library/manga-suggestive-001",
                headers={"Authorization": "Bearer fake-token"},
            )

        row = asyncio.run(
            self.db.fetchone(
                "SELECT content_rating FROM user_library WHERE manga_id = ?",
                "manga-suggestive-001",
            )
        )
        self.assertEqual(row["content_rating"], "suggestive")

    # -- Library age filtering ------------------------------------------------

    def test_get_library_filters_by_age(self):
        """Library should filter out age-restricted manga for underage users."""
        # Set user birth_date so age = 15 (under 16)
        asyncio.run(
            UserService(self.db).update_profile_metadata(
                _FAKE_PAYLOAD.uid,
                username="young_reader",
                birth_date="2011-06-15",
            )
        )

        # Add a safe manga and an erotica manga
        asyncio.run(
            UserService(self.db).add_to_library(
                _FAKE_PAYLOAD.uid,
                "manga-safe-001",
                title="Safe Manga",
                content_rating="safe",
            )
        )
        asyncio.run(
            UserService(self.db).add_to_library(
                _FAKE_PAYLOAD.uid,
                "manga-erotica-001",
                title="Erotica Manga",
                content_rating="erotica",
            )
        )

        self.app.dependency_overrides[get_user_age] = lambda: 15

        with TestClient(self.app) as client:
            response = client.get(
                "/users/me/library",
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "manga-safe-001")

    def test_get_library_allows_age_appropriate_content(self):
        """Library should show age-appropriate manga for users of sufficient age."""
        # Set user birth_date so age = 20 (over 18)
        asyncio.run(
            UserService(self.db).update_profile_metadata(
                _FAKE_PAYLOAD.uid,
                username="adult_reader",
                birth_date="2006-06-15",
            )
        )

        # Add safe and erotica manga
        asyncio.run(
            UserService(self.db).add_to_library(
                _FAKE_PAYLOAD.uid,
                "manga-safe-001",
                title="Safe Manga",
                content_rating="safe",
            )
        )
        asyncio.run(
            UserService(self.db).add_to_library(
                _FAKE_PAYLOAD.uid,
                "manga-erotica-001",
                title="Erotica Manga",
                content_rating="erotica",
            )
        )

        self.app.dependency_overrides[get_user_age] = lambda: 20

        with TestClient(self.app) as client:
            response = client.get(
                "/users/me/library",
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        ids = {m["id"] for m in data}
        self.assertIn("manga-safe-001", ids)
        self.assertIn("manga-erotica-001", ids)

    def test_get_library_guest_sees_only_safe(self):
        """Guest users (no birth_date) should only see safe manga in library."""
        asyncio.run(
            UserService(self.db).add_to_library(
                _FAKE_PAYLOAD.uid,
                "manga-safe-001",
                title="Safe Manga",
                content_rating="safe",
            )
        )
        asyncio.run(
            UserService(self.db).add_to_library(
                _FAKE_PAYLOAD.uid,
                "manga-erotica-001",
                title="Erotica Manga",
                content_rating="erotica",
            )
        )

        # get_user_age returns None for guest
        self.app.dependency_overrides[get_user_age] = lambda: None

        with TestClient(self.app) as client:
            response = client.get(
                "/users/me/library",
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "manga-safe-001")

    def test_openapi_library_item_route_includes_patch(self):
        with TestClient(self.app) as client:
            response = client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        path_item = response.json()["paths"]["/users/me/library/{manga_id}"]
        self.assertIn("post", path_item)
        self.assertIn("patch", path_item)
        self.assertIn("delete", path_item)

    def test_openapi_me_route_includes_patch_contract(self):
        with TestClient(self.app) as client:
            response = client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        openapi = response.json()
        path_item = openapi["paths"]["/users/me"]
        self.assertIn("get", path_item)
        self.assertIn("patch", path_item)
        patch_operation = path_item["patch"]
        self.assertEqual(
            patch_operation["requestBody"]["content"]["application/json"]["schema"][
                "$ref"
            ],
            "#/components/schemas/UpdateUserProfileRequest",
        )
        self.assertEqual(
            patch_operation["responses"]["200"]["content"]["application/json"][
                "schema"
            ]["$ref"],
            "#/components/schemas/UserProfile",
        )
        request_schema = openapi["components"]["schemas"]["UpdateUserProfileRequest"][
            "properties"
        ]
        response_schema = openapi["components"]["schemas"]["UserProfile"]["properties"]
        self.assertIn("username", request_schema)
        self.assertIn("birth_date", request_schema)
        self.assertIn("username", response_schema)
        self.assertIn("birth_date", response_schema)


class UserAccountDeletionTests(unittest.TestCase):
    """Tests for DELETE /users/me account deletion."""

    def setUp(self):
        self.app = create_hermetic_test_app()
        self.db = asyncio.run(_make_test_db())
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_user] = self._fake_auth

        # Bootstrap user + library entry + preferences.
        svc = UserService(self.db)
        asyncio.run(svc.get_or_create_user(_FAKE_PAYLOAD))
        asyncio.run(svc.add_to_library(_FAKE_PAYLOAD.uid, "manga-1"))
        asyncio.run(svc.get_preferences(_FAKE_PAYLOAD.uid))

    def tearDown(self):
        self.app.dependency_overrides.clear()
        asyncio.run(self.db.close())

    @staticmethod
    async def _fake_auth() -> FirebaseTokenPayload:
        return _FAKE_PAYLOAD

    # -- Happy path ----------------------------------------------------------

    def test_delete_me_removes_user_and_data(self):
        with (
            patch("app.services.user_service.firebase_admin._apps", [True]),
            patch(
                "app.services.user_service.firebase_admin.auth.delete_user"
            ) as mock_delete_user,
        ):
            mock_delete_user.return_value = None
            with TestClient(self.app) as client:
                response = client.delete(
                    "/users/me",
                    headers={"Authorization": "Bearer fake-token"},
                )

        self.assertEqual(response.status_code, 204)
        mock_delete_user.assert_called_once_with(_FAKE_PAYLOAD.uid)

        # Verify local data is gone.
        user = asyncio.run(
            self.db.fetchone(
                "SELECT firebase_uid FROM users WHERE firebase_uid = ?",
                _FAKE_PAYLOAD.uid,
            )
        )
        self.assertIsNone(user)

    def test_delete_me_cleans_library_and_preferences(self):
        with (
            patch("app.services.user_service.firebase_admin._apps", [True]),
            patch("app.services.user_service.firebase_admin.auth.delete_user"),
        ):
            with TestClient(self.app) as client:
                client.delete(
                    "/users/me",
                    headers={"Authorization": "Bearer fake-token"},
                )

        library = asyncio.run(
            self.db.fetchall(
                "SELECT * FROM user_library WHERE firebase_uid = ?",
                _FAKE_PAYLOAD.uid,
            )
        )
        prefs = asyncio.run(
            self.db.fetchone(
                "SELECT * FROM reading_preferences WHERE firebase_uid = ?",
                _FAKE_PAYLOAD.uid,
            )
        )
        user = asyncio.run(
            self.db.fetchone(
                "SELECT * FROM users WHERE firebase_uid = ?",
                _FAKE_PAYLOAD.uid,
            )
        )
        self.assertEqual(len(library), 0)
        self.assertIsNone(prefs)
        self.assertIsNone(user)

    # -- Idempotency ---------------------------------------------------------

    def test_delete_me_idempotent_repeat(self):
        with (
            patch("app.services.user_service.firebase_admin._apps", [True]),
            patch(
                "app.services.user_service.firebase_admin.auth.delete_user",
                side_effect=firebase_auth_sdk.UserNotFoundError("not found"),
            ),
        ):
            with TestClient(self.app) as client:
                # First call.
                response1 = client.delete(
                    "/users/me",
                    headers={"Authorization": "Bearer fake-token"},
                )
                self.assertEqual(response1.status_code, 204)

                # Second call — same behavior, user already gone.
                response2 = client.delete(
                    "/users/me",
                    headers={"Authorization": "Bearer fake-token"},
                )

        self.assertEqual(response2.status_code, 204)

        # Verify data was still cleaned up.
        user = asyncio.run(
            self.db.fetchone(
                "SELECT firebase_uid FROM users WHERE firebase_uid = ?",
                _FAKE_PAYLOAD.uid,
            )
        )
        self.assertIsNone(user)

    # -- Firebase failure ----------------------------------------------------

    def test_delete_me_firebase_failure_aborts(self):
        with (
            patch("app.services.user_service.firebase_admin._apps", [True]),
            patch(
                "app.services.user_service.firebase_admin.auth.delete_user",
                side_effect=RuntimeError("Firebase timeout"),
            ),
        ):
            with TestClient(self.app) as client:
                response = client.delete(
                    "/users/me",
                    headers={"Authorization": "Bearer fake-token"},
                )

        self.assertEqual(response.status_code, 502)

        # Verify ALL local data is preserved (no partial cleanup).
        user = asyncio.run(
            self.db.fetchone(
                "SELECT firebase_uid FROM users WHERE firebase_uid = ?",
                _FAKE_PAYLOAD.uid,
            )
        )
        self.assertIsNotNone(user)

        library = asyncio.run(
            self.db.fetchall(
                "SELECT * FROM user_library WHERE firebase_uid = ?",
                _FAKE_PAYLOAD.uid,
            )
        )
        self.assertEqual(len(library), 1)

        prefs = asyncio.run(
            self.db.fetchone(
                "SELECT * FROM reading_preferences WHERE firebase_uid = ?",
                _FAKE_PAYLOAD.uid,
            )
        )
        self.assertIsNotNone(prefs)

    # -- CI/test mode (Firebase not initialized) -----------------------------

    def test_delete_me_skips_firebase_when_not_initialized(self):
        with patch("app.services.user_service.firebase_admin._apps", []):
            with TestClient(self.app) as client:
                response = client.delete(
                    "/users/me",
                    headers={"Authorization": "Bearer fake-token"},
                )

        self.assertEqual(response.status_code, 204)

        # Verify local data is gone despite no Firebase init.
        user = asyncio.run(
            self.db.fetchone(
                "SELECT firebase_uid FROM users WHERE firebase_uid = ?",
                _FAKE_PAYLOAD.uid,
            )
        )
        self.assertIsNone(user)

    # -- Unauthenticated -----------------------------------------------------

    def test_delete_me_unauthenticated(self):
        # Temporarily remove the auth override so real auth is enforced.
        self.app.dependency_overrides.pop(get_current_user, None)
        with TestClient(self.app) as client:
            response = client.delete("/users/me")

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
