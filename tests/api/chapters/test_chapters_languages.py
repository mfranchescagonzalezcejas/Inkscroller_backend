"""Tests for the chapter language discovery endpoint."""

import unittest
from importlib.util import find_spec

if find_spec("fastapi") is None:
    raise unittest.SkipTest("fastapi is not installed")

from app.core.dependencies import (
    get_chapter_service,
    get_manga_service,
    get_user_age,
)
from fastapi.testclient import TestClient
from tests.api.chapters.test_chapters_age import (
    FakeChapterService,
    FakeMangaServiceWithAge,
    _make_manga,
)
from tests.api.helpers import create_hermetic_test_app


class TestChapterLanguagesEndpoint(unittest.TestCase):
    """GET /chapters/manga/{manga_id}/languages discovery endpoint."""

    MANGA_DB = {
        "safe-1": _make_manga("safe-1", "One Piece", "safe"),
        "suggestive-1": _make_manga("suggestive-1", "Berserk", "suggestive"),
    }

    CHAPTERS = [
        {
            "id": "ch-1",
            "number": "1",
            "title": "Chapter 1",
            "date": "2026-01-01T00:00:00Z",
            "language": "en",
            "readable": True,
            "external": False,
            "externalUrl": None,
        },
        {
            "id": "ch-2",
            "number": "2",
            "title": "Chapter 2",
            "date": "2026-01-02T00:00:00Z",
            "language": "es",
            "readable": True,
            "external": False,
            "externalUrl": None,
        },
        {
            "id": "ch-3",
            "number": "3",
            "title": "Chapter 3",
            "date": "2026-01-03T00:00:00Z",
            "language": "en",
            "readable": True,
            "external": False,
            "externalUrl": None,
        },
    ]

    def setUp(self):
        self.app = create_hermetic_test_app()

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def _override(self, user_age=None):
        self.app.dependency_overrides[get_manga_service] = lambda: (
            FakeMangaServiceWithAge(self.MANGA_DB)
        )
        self.app.dependency_overrides[get_chapter_service] = lambda: FakeChapterService(
            self.CHAPTERS
        )
        self.app.dependency_overrides[get_user_age] = lambda: user_age

    def test_languages_endpoint_returns_unique_sorted(self):
        """Guest discovers unique sorted languages for an accessible manga."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/safe-1/languages")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ["en", "es"])

    def test_languages_endpoint_returns_empty_for_accessible_manga(self):
        """Accessible manga with no eligible chapters returns empty list."""
        self.app.dependency_overrides[get_manga_service] = lambda: (
            FakeMangaServiceWithAge(self.MANGA_DB)
        )
        self.app.dependency_overrides[get_chapter_service] = lambda: FakeChapterService(
            []
        )
        self.app.dependency_overrides[get_user_age] = lambda: None

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/safe-1/languages")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_languages_endpoint_returns_403_for_age_restricted(self):
        """Guests cannot discover languages for age-restricted manga."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/suggestive-1/languages")

        self.assertEqual(response.status_code, 403)
        self.assertIn("age-restricted", response.json()["detail"])

    def test_languages_endpoint_returns_404_for_unknown_manga(self):
        """Unknown manga returns 404 on language discovery."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/nonexistent-id/languages")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
