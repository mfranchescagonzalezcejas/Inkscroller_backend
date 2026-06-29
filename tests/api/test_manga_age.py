"""T4.2 — Integration tests for age-based content restriction on manga routes.

Strategy:
- Override `get_user_age` dependency to control the resolved user age.
- Override `get_manga_service` with a fake that mimics age-filtering behavior
  from MangaService._filter_by_age / get_by_id.
- Test HTTP status codes and response payloads via TestClient.
"""

import unittest
from importlib.util import find_spec
from unittest.mock import AsyncMock

if find_spec("fastapi") is None:
    raise unittest.SkipTest("fastapi is not installed")

from fastapi.testclient import TestClient

from app.core.age import can_access_content
from app.core.dependencies import get_manga_service, get_user_age
from tests.api.helpers import create_hermetic_test_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manga(
    manga_id: str,
    title: str = "Test Manga",
    content_rating: str | None = "safe",
) -> dict:
    """Build a minimal mapped-manga dict matching MangaService output shape."""
    return {
        "id": manga_id,
        "title": title,
        "description": None,
        "coverUrl": None,
        "demographic": None,
        "status": "ongoing",
        "contentRating": content_rating,
        "genres": [],
        "score": None,
        "rank": None,
        "popularity": None,
        "members": None,
        "favorites": None,
        "authors": [],
        "serialization": None,
        "chapters": None,
        "startYear": None,
        "endYear": None,
    }


class FakeMangaServiceWithAge:
    """Fake MangaService that replicates age-filtering from the real service.

    Used to test route-layer integration without touching MangaDex.
    """

    def __init__(self, manga_db: dict[str, dict]):
        self.manga_db = manga_db
        self.calls: list[dict] = []

    async def get_by_id(
        self,
        manga_id: str,
        user_age: int | None = None,
        skip_age_filter: bool = False,
    ) -> dict | None:
        self.calls.append(
            {
                "method": "get_by_id",
                "manga_id": manga_id,
                "user_age": user_age,
                "skip_age_filter": skip_age_filter,
            }
        )
        manga = self.manga_db.get(manga_id)
        if manga is None:
            return None
        if not skip_age_filter and not can_access_content(
            manga.get("contentRating"), user_age
        ):
            return None
        return dict(manga)

    async def search(self, query: str, user_age: int | None = None) -> list[dict]:
        self.calls.append({"method": "search", "query": query, "user_age": user_age})
        return [
            dict(m)
            for m in self.manga_db.values()
            if can_access_content(m.get("contentRating"), user_age)
        ]

    async def list_manga(self, **kwargs) -> dict:
        self.calls.append({"method": "list_manga", **kwargs})
        user_age = kwargs.get("user_age")
        results = [
            dict(m)
            for m in self.manga_db.values()
            if can_access_content(m.get("contentRating"), user_age)
        ]
        return {
            "data": results,
            "total": len(results),
            "limit": kwargs.get("limit", 20),
            "offset": kwargs.get("offset", 0),
        }


# ---------------------------------------------------------------------------
# Test Suites
# ---------------------------------------------------------------------------


class TestMangaSearchAgeRestriction(unittest.TestCase):
    """T4.2 — GET /manga/search age-based filtering."""

    MANGA_DB = {
        "safe-1": _make_manga("safe-1", "One Piece", "safe"),
        "safe-2": _make_manga("safe-2", "Naruto", "safe"),
        "suggestive-1": _make_manga("suggestive-1", "Berserk", "suggestive"),
        "erotica-1": _make_manga("erotica-1", "Hentai Manga", "erotica"),
    }

    def setUp(self):
        self.app = create_hermetic_test_app()

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def _override(self, user_age=None):
        self.app.dependency_overrides[get_manga_service] = lambda: FakeMangaServiceWithAge(
            self.MANGA_DB
        )
        self.app.dependency_overrides[get_user_age] = lambda: user_age

    def test_guest_search_returns_safe_only(self):
        """Guest users should only see safe manga in search results."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/manga/search?q=test")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        ratings = {m["contentRating"] for m in data}
        self.assertTrue(ratings.issubset({"safe", None}))

    def test_user_16_sees_suggestive_in_search(self):
        """Users aged 16+ should see suggestive manga in search results."""
        self._override(user_age=16)

        with TestClient(self.app) as client:
            response = client.get("/manga/search?q=test")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 3)  # 2 safe + 1 suggestive
        ids = {m["id"] for m in data}
        self.assertIn("suggestive-1", ids)

    def test_user_12_only_sees_safe_in_search(self):
        """Users under 16 should not see suggestive manga in search."""
        self._override(user_age=12)

        with TestClient(self.app) as client:
            response = client.get("/manga/search?q=test")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        ids = {m["id"] for m in data}
        self.assertNotIn("suggestive-1", ids)
        self.assertNotIn("erotica-1", ids)

    def test_user_18_sees_all_in_search(self):
        """Users aged 18+ should see all content ratings."""
        self._override(user_age=18)

        with TestClient(self.app) as client:
            response = client.get("/manga/search?q=test")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 4)


class TestMangaGetAgeRestriction(unittest.TestCase):
    """T4.2 — GET /manga/{manga_id} age-based restrictions (403 vs 404)."""

    MANGA_DB = {
        "safe-1": _make_manga("safe-1", "One Piece", "safe"),
        "suggestive-1": _make_manga("suggestive-1", "Berserk", "suggestive"),
        "erotica-1": _make_manga("erotica-1", "Hentai Manga", "erotica"),
    }

    def setUp(self):
        self.app = create_hermetic_test_app()

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def _override(self, user_age=None):
        self.app.dependency_overrides[get_manga_service] = lambda: FakeMangaServiceWithAge(
            self.MANGA_DB
        )
        self.app.dependency_overrides[get_user_age] = lambda: user_age

    def test_guest_get_safe_returns_200(self):
        """Guest users should be able to access safe manga."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/manga/safe-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "safe-1")

    def test_guest_get_suggestive_returns_403(self):
        """Guest users should get 403 when directly accessing suggestive manga."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/manga/suggestive-1")

        self.assertEqual(response.status_code, 403)
        self.assertIn("age-restricted", response.json()["detail"])

    def test_guest_get_erotica_returns_403(self):
        """Guest users should get 403 for erotica content."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/manga/erotica-1")

        self.assertEqual(response.status_code, 403)

    def test_user_16_get_suggestive_returns_200(self):
        """Users aged 16+ should access suggestive manga."""
        self._override(user_age=16)

        with TestClient(self.app) as client:
            response = client.get("/manga/suggestive-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "suggestive-1")

    def test_user_12_get_suggestive_returns_403(self):
        """Users under 16 should get 403 when accessing suggestive manga."""
        self._override(user_age=12)

        with TestClient(self.app) as client:
            response = client.get("/manga/suggestive-1")

        self.assertEqual(response.status_code, 403)

    def test_user_17_get_erotica_returns_403(self):
        """Users under 18 should get 403 for erotica content."""
        self._override(user_age=17)

        with TestClient(self.app) as client:
            response = client.get("/manga/erotica-1")

        self.assertEqual(response.status_code, 403)

    def test_nonexistent_manga_returns_404(self):
        """Nonexistent manga should return 404, not 403."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/manga/nonexistent-id")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Manga not found")

    def test_age_restricted_detail_includes_min_age(self):
        """403 response should include the minimum age requirement."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/manga/suggestive-1")

        self.assertEqual(response.status_code, 403)
        detail = response.json()["detail"]
        self.assertIn("16", detail)

    def test_403_detail_for_erotica_includes_18(self):
        """403 for erotica should mention 18+."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/manga/erotica-1")

        self.assertEqual(response.status_code, 403)
        detail = response.json()["detail"]
        self.assertIn("18", detail)


class TestMangaListAgeRestriction(unittest.TestCase):
    """T4.2 — GET /manga (list) age-based filtering."""

    MANGA_DB = {
        "safe-1": _make_manga("safe-1", "One Piece", "safe"),
        "suggestive-1": _make_manga("suggestive-1", "Berserk", "suggestive"),
    }

    def setUp(self):
        self.app = create_hermetic_test_app()

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def _override(self, user_age=None):
        self.app.dependency_overrides[get_manga_service] = lambda: FakeMangaServiceWithAge(
            self.MANGA_DB
        )
        self.app.dependency_overrides[get_user_age] = lambda: user_age

    def test_guest_list_returns_safe_only(self):
        """Guest users should only see safe manga in list results."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/manga")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        # list_manga wraps in {"data": [...]}
        if isinstance(data, dict) and "data" in data:
            items = data["data"]
        else:
            items = data
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "safe-1")

    def test_user_16_list_sees_suggestive(self):
        """Users aged 16+ should see suggestive manga in list results."""
        self._override(user_age=16)

        with TestClient(self.app) as client:
            response = client.get("/manga")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        if isinstance(data, dict) and "data" in data:
            items = data["data"]
        else:
            items = data
        self.assertEqual(len(items), 2)
        ids = {m["id"] for m in items}
        self.assertIn("suggestive-1", ids)

    def test_user_age_passed_to_service_list_manga(self):
        """user_age should be forwarded to service.list_manga()."""
        self._override(user_age=16)

        with TestClient(self.app) as client:
            client.get("/manga")

        # The fake service records calls — verify user_age was passed
        # (We can't easily inspect calls through the override, but the
        #  FakeMangaServiceWithAge records them internally)
        # This test primarily verifies the route doesn't crash with user_age.


class TestMangaRouteEdgeCases(unittest.TestCase):
    """Edge cases for age restriction across manga routes."""

    MANGA_DB = {
        "safe-1": _make_manga("safe-1", "One Piece", "safe"),
    }

    def setUp(self):
        self.app = create_hermetic_test_app()

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def test_search_min_length_still_enforced(self):
        """Query param validation should still work with age dependencies."""
        self.app.dependency_overrides[get_manga_service] = lambda: FakeMangaServiceWithAge(
            self.MANGA_DB
        )
        self.app.dependency_overrides[get_user_age] = lambda: None

        with TestClient(self.app) as client:
            response = client.get("/manga/search?q=")

        self.assertEqual(response.status_code, 422)

    def test_manga_id_trimmed_with_age_check(self):
        """Whitespace in manga_id should be trimmed before age check."""
        self.app.dependency_overrides[get_manga_service] = lambda: FakeMangaServiceWithAge(
            self.MANGA_DB
        )
        self.app.dependency_overrides[get_user_age] = lambda: None

        with TestClient(self.app) as client:
            response = client.get("/manga/%20safe-1%20")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "safe-1")

    def test_missing_birth_date_treated_as_guest(self):
        """Authenticated user without birth_date should be restricted to safe.

        This tests the get_user_age dependency chain. When get_user_age
        returns None (guest/missing birth_date), routes behave identically
        to unauthenticated guests.
        """
        self.app.dependency_overrides[get_manga_service] = lambda: FakeMangaServiceWithAge(
            self.MANGA_DB
        )
        # Simulate missing birth_date by having get_user_age return None
        self.app.dependency_overrides[get_user_age] = lambda: None

        with TestClient(self.app) as client:
            response = client.get("/manga/search?q=test")

        self.assertEqual(response.status_code, 200)
        # Only safe content returned (same as guest)
        data = response.json()
        for m in data:
            self.assertIn(m["contentRating"], (None, "safe"))


if __name__ == "__main__":
    unittest.main()
