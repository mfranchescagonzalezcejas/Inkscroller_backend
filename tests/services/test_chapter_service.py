import unittest
from unittest.mock import AsyncMock, call

from app.core.cache import SimpleCache
from app.services.chapter_service import ChapterService


def _chapter(
    chapter_id: str,
    manga_id: str = "manga-1",
    language: str = "en",
    pages: int = 1,
    external_url: str | None = None,
) -> dict:
    return {
        "id": chapter_id,
        "attributes": {
            "chapter": chapter_id,
            "translatedLanguage": language,
            "pages": pages,
            "publishAt": "2024-01-01T00:00:00Z",
            "externalUrl": external_url,
        },
        "relationships": [{"type": "manga", "id": manga_id}],
    }


class TestChapterService(unittest.IsolatedAsyncioTestCase):
    async def test_get_chapters_fetches_all_pages(self):
        client = AsyncMock()
        client.get_chapters.side_effect = [
            {"data": [_chapter(str(index)) for index in range(100)], "total": 101},
            {"data": [_chapter("100")], "total": 101},
        ]
        service = ChapterService(client, SimpleCache())

        result = await service.get_chapters("manga-1")

        self.assertEqual(len(result), 101)
        client.get_chapters.assert_has_awaits(
            [
                call(manga_id="manga-1", language="en", limit=100, offset=0),
                call(manga_id="manga-1", language="en", limit=100, offset=100),
            ]
        )

    async def test_latest_chapters_filters_manga_by_age(self):
        client = AsyncMock()
        client.get_latest_chapters.return_value = {
            "data": [
                _chapter("safe-chapter", "safe-manga"),
                _chapter("adult-chapter", "adult-manga"),
            ]
        }
        client.get_manga_list_by_ids.return_value = {
            "data": [
                {
                    "id": "safe-manga",
                    "attributes": {
                        "title": {"en": "Safe Manga"},
                        "publicationDemographic": "shounen",
                        "contentRating": "safe",
                    },
                    "relationships": [],
                },
                {
                    "id": "adult-manga",
                    "attributes": {
                        "title": {"en": "Adult Manga"},
                        "publicationDemographic": "seinen",
                        "contentRating": "erotica",
                    },
                    "relationships": [],
                },
            ]
        }
        service = ChapterService(client, SimpleCache())

        result = await service.get_latest_home_chapters(user_age=12)

        self.assertEqual([item["mangaId"] for item in result], ["safe-manga"])

    async def test_get_available_languages_returns_unique_sorted(self):
        client = AsyncMock()
        client.get_chapters.return_value = {
            "data": [
                _chapter("ch-1", language="en"),
                _chapter("ch-2", language="es"),
                _chapter("ch-3", language="en"),
            ],
            "total": 3,
        }
        service = ChapterService(client, SimpleCache())

        result = await service.get_available_languages("manga-1")

        self.assertEqual(result, ["en", "es"])

    async def test_get_available_languages_paginates_all_pages(self):
        client = AsyncMock()
        client.get_chapters.side_effect = [
            {
                "data": [_chapter("ch-1", language="en") for _ in range(500)],
                "total": 501,
            },
            {"data": [_chapter("ch-2", language="es")], "total": 501},
        ]
        service = ChapterService(client, SimpleCache())

        result = await service.get_available_languages("manga-1")

        self.assertEqual(result, ["en", "es"])
        client.get_chapters.assert_has_awaits(
            [
                call(manga_id="manga-1", language=None, limit=500, offset=0),
                call(manga_id="manga-1", language=None, limit=500, offset=500),
            ]
        )

    async def test_get_available_languages_caches_result(self):
        client = AsyncMock()
        client.get_chapters.return_value = {
            "data": [_chapter("ch-1", language="en")],
            "total": 1,
        }
        service = ChapterService(client, SimpleCache())

        first = await service.get_available_languages("manga-1")
        second = await service.get_available_languages("manga-1")

        self.assertEqual(first, second)
        client.get_chapters.assert_awaited_once_with(
            manga_id="manga-1", language=None, limit=500, offset=0
        )

    async def test_get_available_languages_filters_eligible_only(self):
        client = AsyncMock()
        client.get_chapters.return_value = {
            "data": [
                _chapter("ch-1", language="en", pages=0),
                _chapter(
                    "ch-2",
                    language="es",
                    pages=0,
                    external_url="https://example.com",
                ),
            ],
            "total": 2,
        }
        service = ChapterService(client, SimpleCache())

        result = await service.get_available_languages("manga-1")

        self.assertEqual(result, ["es"])

    async def test_get_available_languages_all_ineligible_returns_empty(self):
        """When ALL chapters have pages=0 and no externalUrl → empty list."""
        client = AsyncMock()
        client.get_chapters.return_value = {
            "data": [
                _chapter("ch-1", language="en", pages=0),
                _chapter("ch-2", language="en", pages=0),
            ],
            "total": 2,
        }
        service = ChapterService(client, SimpleCache())

        result = await service.get_available_languages("manga-1")

        self.assertEqual(result, [])
