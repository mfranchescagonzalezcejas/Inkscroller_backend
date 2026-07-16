import unittest
from unittest.mock import AsyncMock, call

from app.core.cache import SimpleCache
from app.services.chapter_service import ChapterService


def _chapter(chapter_id: str, manga_id: str = "manga-1") -> dict:
    return {
        "id": chapter_id,
        "attributes": {
            "chapter": chapter_id,
            "pages": 1,
            "publishAt": "2024-01-01T00:00:00Z",
            "externalUrl": None,
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
