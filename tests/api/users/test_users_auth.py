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
from unittest.mock import AsyncMock

if find_spec("fastapi") is None or find_spec("dotenv") is None:
    raise unittest.SkipTest("fastapi/python-dotenv not installed")

from fastapi.testclient import TestClient

from app.core.database import init_db
from app.core.db_adapter import DatabaseAdapter
from app.core.dependencies import get_current_user, get_db, get_manga_service
from app.core.exceptions import ProfileConflictError
from app.core.firebase_auth import FirebaseTokenPayload
from app.models.manga import Manga
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

_FAKE_MANGA = Manga(
    id="manga-abc-123",
    title="Test Manga",
    description="A test manga",
    coverUrl=None,
)


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

    def test_patch_me_null_birth_date_clears_only_birth_date(self):
        with TestClient(self.app) as client:
            client.patch(
                "/users/me",
                json={"username": "reader-five", "birth_date": "2001-01-20"},
                headers={"Authorization": "Bearer fake-token"},
            )
            response = client.patch(
                "/users/me",
                json={"birth_date": None},
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["username"], "reader-five")
        self.assertIsNone(data["birth_date"])

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
        self.assertEqual(data[0]["id"], _FAKE_MANGA.id)
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


if __name__ == "__main__":
    unittest.main()
