"""Tests for age-based content restriction on chapter routes.

Strategy:
- Override `get_user_age` dependency to control the resolved user age.
- Override `get_manga_service` and `get_chapter_service` with fakes.
- Test HTTP status codes and response payloads via TestClient.
"""

import unittest
from importlib.util import find_spec
from unittest.mock import AsyncMock

if find_spec("fastapi") is None:
    raise unittest.SkipTest("fastapi is not installed")

from fastapi.testclient import TestClient

from app.core.age import can_access_content
from app.core.dependencies import (
    get_chapter_service,
    get_manga_service,
    get_user_age,
)
from app.core.dependencies import get_chapter_pages_service
from tests.api.helpers import create_hermetic_test_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeChapterPagesService:
    """Fake pages service that returns a minimal page response."""

    def __init__(self):
        self.received_id = None

    async def get_pages(self, chapter_id: str) -> dict:
        self.received_id = chapter_id
        return {
            "hash": "abc123",
            "data": ["page-1.jpg"],
            "readable": True,
            "external": False,
            "externalUrl": None,
        }


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
        "contentRating": content_rating,
    }


class FakeMangaServiceWithAge:
    """Fake MangaService that replicates age-filtering from the real service."""

    def __init__(self, manga_db: dict[str, dict]):
        self.manga_db = manga_db

    async def get_by_id(
        self,
        manga_id: str,
        user_age: int | None = None,
        skip_age_filter: bool = False,
    ) -> dict | None:
        manga = self.manga_db.get(manga_id)
        if manga is None:
            return None
        if not skip_age_filter and not can_access_content(
            manga.get("contentRating"), user_age
        ):
            return None
        return dict(manga)


class FakeChapterService:
    """Fake ChapterService that returns canned chapters."""

    def __init__(self, chapters: list[dict] | None = None):
        self._chapters = chapters or []
        self._chapter_manga_map: dict[str, str] = {}

    def set_chapter_manga_map(self, mapping: dict[str, str]):
        self._chapter_manga_map = mapping

    async def get_chapters(self, manga_id: str, language: str = "en") -> list[dict]:
        return list(self._chapters)

    async def get_manga_id_for_chapter(self, chapter_id: str) -> str | None:
        return self._chapter_manga_map.get(chapter_id)


# ---------------------------------------------------------------------------
# Test Suites
# ---------------------------------------------------------------------------


class TestChaptersAgeRestriction(unittest.TestCase):
    """GET /chapters/manga/{manga_id} age-based restrictions (403 vs 200)."""

    MANGA_DB = {
        "safe-1": _make_manga("safe-1", "One Piece", "safe"),
        "suggestive-1": _make_manga("suggestive-1", "Berserk", "suggestive"),
        "erotica-1": _make_manga("erotica-1", "Hentai Manga", "erotica"),
    }

    CHAPTERS = [
        {
            "id": "ch-1",
            "number": "1",
            "title": "Chapter 1",
            "date": "2026-01-01T00:00:00Z",
            "readable": True,
            "external": False,
            "externalUrl": None,
        },
        {
            "id": "ch-2",
            "number": "2",
            "title": "Chapter 2",
            "date": "2026-01-02T00:00:00Z",
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
        self.app.dependency_overrides[get_manga_service] = lambda: FakeMangaServiceWithAge(
            self.MANGA_DB
        )
        self.app.dependency_overrides[get_chapter_service] = lambda: FakeChapterService(
            self.CHAPTERS
        )
        self.app.dependency_overrides[get_user_age] = lambda: user_age

    def test_guest_get_safe_manga_chapters_returns_200(self):
        """Guest users should be able to get chapters for safe manga."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/safe-1")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)

    def test_guest_get_suggestive_manga_chapters_returns_403(self):
        """Guest users should get 403 for age-restricted manga chapters."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/suggestive-1")

        self.assertEqual(response.status_code, 403)
        self.assertIn("age-restricted", response.json()["detail"])

    def test_guest_get_erotica_manga_chapters_returns_403(self):
        """Guest users should get 403 for erotica manga chapters."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/erotica-1")

        self.assertEqual(response.status_code, 403)

    def test_user_16_get_suggestive_manga_chapters_returns_200(self):
        """Users aged 16+ should get chapters for suggestive manga."""
        self._override(user_age=16)

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/suggestive-1")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)

    def test_user_12_get_suggestive_manga_chapters_returns_403(self):
        """Users under 16 should get 403 for suggestive manga chapters."""
        self._override(user_age=12)

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/suggestive-1")

        self.assertEqual(response.status_code, 403)

    def test_user_18_get_erotica_manga_chapters_returns_200(self):
        """Users aged 18+ should get chapters for erotica manga."""
        self._override(user_age=18)

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/erotica-1")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)

    def test_nonexistent_manga_returns_404(self):
        """Nonexistent manga should return 404."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/nonexistent-id")

        self.assertEqual(response.status_code, 404)

    def test_403_detail_includes_min_age_for_suggestive(self):
        """403 response should include the minimum age requirement."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/suggestive-1")

        self.assertEqual(response.status_code, 403)
        detail = response.json()["detail"]
        self.assertIn("16", detail)

    def test_403_detail_includes_18_for_erotica(self):
        """403 for erotica should mention 18+."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/erotica-1")

        self.assertEqual(response.status_code, 403)
        detail = response.json()["detail"]
        self.assertIn("18", detail)



class TestChapterPagesAgeRestriction(unittest.TestCase):
    """GET /chapters/{chapter_id}/pages age-based restrictions."""

    MANGA_DB = {
        "safe-1": _make_manga("safe-1", "One Piece", "safe"),
        "suggestive-1": _make_manga("suggestive-1", "Berserk", "suggestive"),
        "erotica-1": _make_manga("erotica-1", "Hentai Manga", "erotica"),
    }

    CHAPTER_MANGA_MAP = {
        "ch-safe": "safe-1",
        "ch-suggestive": "suggestive-1",
        "ch-erotica": "erotica-1",
        "ch-unknown": "nonexistent-id",
    }

    def setUp(self):
        self.app = create_hermetic_test_app()

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def _override(self, user_age=None):
        manga_svc = FakeMangaServiceWithAge(self.MANGA_DB)
        chapter_svc = FakeChapterService()
        chapter_svc.set_chapter_manga_map(self.CHAPTER_MANGA_MAP)
        pages_svc = FakeChapterPagesService()

        self.app.dependency_overrides[get_manga_service] = lambda: manga_svc
        self.app.dependency_overrides[get_chapter_service] = lambda: chapter_svc
        self.app.dependency_overrides[get_chapter_pages_service] = lambda: pages_svc
        self.app.dependency_overrides[get_user_age] = lambda: user_age

    def test_guest_get_safe_chapter_pages_returns_200(self):
        """Guest should be able to access pages of safe manga chapters."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/chapters/ch-safe/pages")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["readable"], True)

    def test_guest_get_suggestive_chapter_pages_returns_403(self):
        """Guest should get 403 for pages of suggestive manga chapters."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/chapters/ch-suggestive/pages")

        self.assertEqual(response.status_code, 403)
        self.assertIn("age-restricted", response.json()["detail"])

    def test_guest_get_erotica_chapter_pages_returns_403(self):
        """Guest should get 403 for pages of erotica manga chapters."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/chapters/ch-erotica/pages")

        self.assertEqual(response.status_code, 403)

    def test_user_16_get_suggestive_chapter_pages_returns_200(self):
        """Users aged 16+ should access pages of suggestive manga chapters."""
        self._override(user_age=16)

        with TestClient(self.app) as client:
            response = client.get("/chapters/ch-suggestive/pages")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["readable"], True)

    def test_user_12_get_suggestive_chapter_pages_returns_403(self):
        """Users under 16 should get 403 for suggestive manga chapter pages."""
        self._override(user_age=12)

        with TestClient(self.app) as client:
            response = client.get("/chapters/ch-suggestive/pages")

        self.assertEqual(response.status_code, 403)

    def test_pages_unknown_manga_chapter_returns_404(self):
        """If manga lookup fails, fail closed with 404."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/chapters/ch-unknown/pages")

        self.assertEqual(response.status_code, 404)

    def test_pages_403_detail_includes_min_age(self):
        """403 detail should mention the required age."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/chapters/ch-suggestive/pages")

        self.assertEqual(response.status_code, 403)
        detail = response.json()["detail"]
        self.assertIn("16", detail)


if __name__ == "__main__":
    unittest.main()
