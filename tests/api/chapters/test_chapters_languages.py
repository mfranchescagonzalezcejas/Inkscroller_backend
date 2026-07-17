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
        "safe-1": _make_manga(
            "safe-1",
            "One Piece",
            "safe",
            available_translated_languages=["en", "es"],
        ),
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

    def test_languages_default_preferred_lang_en(self):
        """Default preferred_lang=en matches en, returns en chapters."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/safe-1/languages")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["available"], ["en", "es"])
        self.assertEqual(data["matched"], "en")
        self.assertEqual(len(data["chapters"]), 2)
        for ch in data["chapters"]:
            self.assertEqual(ch["language"], "en")

    def test_languages_explicit_preferred_lang_es(self):
        """preferred_lang=es matches es, returns es chapters."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/safe-1/languages?preferred_lang=es")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["matched"], "es")
        self.assertEqual(len(data["chapters"]), 1)
        for ch in data["chapters"]:
            self.assertEqual(ch["language"], "es")

    def test_languages_variant_match(self):
        """preferred_lang=es matches es-la via prefix when available."""
        manga_db = {
            "variant-1": _make_manga(
                "variant-1",
                "Variant Manga",
                "safe",
                available_translated_languages=["en", "es-la"],
            ),
        }
        chapters = [
            {
                "id": "ch-1",
                "number": "1",
                "title": "Chapter 1",
                "date": "2026-01-01T00:00:00Z",
                "language": "es-la",
                "readable": True,
                "external": False,
                "externalUrl": None,
            },
        ]
        self.app.dependency_overrides[get_manga_service] = lambda: (
            FakeMangaServiceWithAge(manga_db)
        )
        self.app.dependency_overrides[get_chapter_service] = lambda: FakeChapterService(
            chapters
        )
        self.app.dependency_overrides[get_user_age] = lambda: None

        with TestClient(self.app) as client:
            response = client.get(
                "/chapters/manga/variant-1/languages?preferred_lang=es"
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["matched"], "es-la")
        self.assertEqual(data["available"], ["en", "es-la"])

    def test_languages_no_match_falls_back_to_first_available(self):
        """preferred_lang=fr not in available → matched = first available (en)."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/safe-1/languages?preferred_lang=fr")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["matched"], "en")
        self.assertEqual(data["available"], ["en", "es"])

    def test_languages_empty_available_no_chapters(self):
        """Manga with no languages → available=[], matched=en, chapters=[]."""
        no_lang_manga = {
            "no-lang-1": _make_manga("no-lang-1", "No Lang", "safe"),
        }
        self.app.dependency_overrides[get_manga_service] = lambda: (
            FakeMangaServiceWithAge(no_lang_manga)
        )
        self.app.dependency_overrides[get_chapter_service] = lambda: FakeChapterService(
            []
        )
        self.app.dependency_overrides[get_user_age] = lambda: None

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/no-lang-1/languages")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["available"], [])
        self.assertEqual(data["matched"], "en")
        self.assertEqual(data["chapters"], [])

    def test_languages_returns_403_for_age_restricted(self):
        """Guests cannot discover languages for age-restricted manga."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/suggestive-1/languages")

        self.assertEqual(response.status_code, 403)
        self.assertIn("age-restricted", response.json()["detail"])

    def test_languages_returns_404_for_unknown_manga(self):
        """Unknown manga returns 404 on language discovery."""
        self._override(user_age=None)

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/nonexistent-id/languages")

        self.assertEqual(response.status_code, 404)

    def test_languages_matched_lang_no_chapters(self):
        """Available languages exist but matched lang has zero chapters."""
        manga_db = {
            "empty-lang-1": _make_manga(
                "empty-lang-1",
                "Empty Lang",
                "safe",
                available_translated_languages=["en", "ja"],
            ),
        }
        # Only English chapters; Japanese has none
        chapters = [
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
        ]
        self.app.dependency_overrides[get_manga_service] = lambda: (
            FakeMangaServiceWithAge(manga_db)
        )
        self.app.dependency_overrides[get_chapter_service] = lambda: FakeChapterService(
            chapters
        )
        self.app.dependency_overrides[get_user_age] = lambda: None

        with TestClient(self.app) as client:
            response = client.get(
                "/chapters/manga/empty-lang-1/languages?preferred_lang=ja"
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["matched"], "ja")
        self.assertEqual(data["chapters"], [])


if __name__ == "__main__":
    unittest.main()
