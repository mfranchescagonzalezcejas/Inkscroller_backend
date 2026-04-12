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
import unittest
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.core.database import init_db
from app.core.db_adapter import DatabaseAdapter
from app.core.dependencies import get_current_user, get_db, get_manga_service
from app.core.firebase_auth import FirebaseTokenPayload
from app.models.manga import Manga
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
        self.app = create_app()
        self.db = asyncio.get_event_loop().run_until_complete(_make_test_db())
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_user] = self._fake_auth

    def tearDown(self):
        self.app.dependency_overrides.clear()
        asyncio.get_event_loop().run_until_complete(self.db.close())

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
        self.app = create_app()
        self.db = asyncio.get_event_loop().run_until_complete(_make_test_db())
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_user] = self._fake_auth

        # Bootstrap user row required by FK constraint.
        asyncio.get_event_loop().run_until_complete(
            UserService(self.db).get_or_create_user(_FAKE_PAYLOAD)
        )

        # Fake MangaService that returns _FAKE_MANGA for any ID.
        fake_manga_service = AsyncMock()
        fake_manga_service.get_by_id = AsyncMock(return_value=_FAKE_MANGA)
        self.app.dependency_overrides[get_manga_service] = lambda: fake_manga_service

    def tearDown(self):
        self.app.dependency_overrides.clear()
        asyncio.get_event_loop().run_until_complete(self.db.close())

    @staticmethod
    async def _fake_auth() -> FirebaseTokenPayload:
        return _FAKE_PAYLOAD

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


if __name__ == "__main__":
    unittest.main()
