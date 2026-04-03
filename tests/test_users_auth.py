"""Tests for Firebase-auth user/preferences endpoints.

Strategy:
- `get_current_user` dependency is overridden with a fake that returns a
  `FirebaseTokenPayload` directly, so no real Firebase Admin SDK call is made.
- An in-memory SQLite database is used via a `get_db` override so tests are
  hermetic and fast.
- Tests cover: valid token flow, missing/invalid token rejection, first-request
  bootstrap, default preferences, and preference update persistence.
"""

import asyncio
import unittest

import aiosqlite
from fastapi.testclient import TestClient

from app.core.database import init_db
from app.core.dependencies import get_current_user, get_db
from app.core.firebase_auth import FirebaseTokenPayload
from app.services.user_service import UserService
from main import create_app

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_FAKE_PAYLOAD = FirebaseTokenPayload(
    uid="test-uid-001",
    email="user@example.com",
    display_name="Test User",
)


async def _make_test_db() -> aiosqlite.Connection:
    """Create an in-memory SQLite DB with the full schema applied."""
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    ddl = """
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS users (
        firebase_uid  TEXT    PRIMARY KEY,
        email         TEXT    NOT NULL,
        display_name  TEXT,
        created_at    TEXT    NOT NULL
    );
    CREATE TABLE IF NOT EXISTS reading_preferences (
        firebase_uid         TEXT    PRIMARY KEY REFERENCES users(firebase_uid),
        default_reader_mode  TEXT    NOT NULL DEFAULT 'vertical',
        default_language     TEXT    NOT NULL DEFAULT 'en',
        updated_at           TEXT    NOT NULL
    );
    """
    for stmt in ddl.strip().split(";"):
        s = stmt.strip()
        if s:
            await db.execute(s)
    await db.commit()
    return db


class UsersEndpointTests(unittest.TestCase):
    """Authenticated /users/me and /users/me/preferences endpoint tests."""

    def setUp(self):
        self.app = create_app()
        # Use asyncio to set up the in-memory DB synchronously.
        self.db = asyncio.get_event_loop().run_until_complete(_make_test_db())

        # Override the DB dependency to use the in-memory SQLite instance.
        self.app.dependency_overrides[get_db] = lambda: self.db
        # Override auth to return a fake authenticated user.
        self.app.dependency_overrides[get_current_user] = self._fake_auth

    def tearDown(self):
        self.app.dependency_overrides.clear()
        asyncio.get_event_loop().run_until_complete(self.db.close())

    @staticmethod
    async def _fake_auth() -> FirebaseTokenPayload:
        """Dependency override: returns a fake valid token payload."""
        # Also bootstrap the user row so /me endpoints find data.
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

    def test_get_me_returns_same_user_on_second_request(self):
        with TestClient(self.app) as client:
            client.get("/users/me", headers={"Authorization": "Bearer fake-token"})
            response = client.get(
                "/users/me",
                headers={"Authorization": "Bearer fake-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["firebase_uid"], _FAKE_PAYLOAD.uid)

    # -- GET /users/me/preferences --------------------------------------------

    def test_get_preferences_returns_defaults_on_first_request(self):
        # Bootstrap the user first (required by FK constraint).
        asyncio.get_event_loop().run_until_complete(
            UserService(self.db).get_or_create_user(_FAKE_PAYLOAD)
        )

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
        asyncio.get_event_loop().run_until_complete(
            UserService(self.db).get_or_create_user(_FAKE_PAYLOAD)
        )

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
        asyncio.get_event_loop().run_until_complete(
            UserService(self.db).get_or_create_user(_FAKE_PAYLOAD)
        )

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
        # Remove the auth override so the real dependency chain runs.
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


if __name__ == "__main__":
    unittest.main()
