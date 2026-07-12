import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.manga_service import MangaService


def _make_manga(manga_id: str, content_rating: str | None = None) -> dict:
    """Helper to build a minimal mapped manga dict."""
    return {
        "id": manga_id,
        "title": f"Manga {manga_id}",
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


def _raw_mangadex_item(
    manga_id: str,
    content_rating: str | None = None,
    demographic: str = "shounen",
) -> dict:
    """Build a raw MangaDex API item (as returned by the client)."""
    attrs: dict = {
        "title": {"en": f"Manga {manga_id}"},
        "publicationDemographic": demographic,
        "tags": [],
    }
    if content_rating is not None:
        attrs["contentRating"] = content_rating
    return {
        "id": manga_id,
        "attributes": attrs,
        "relationships": [],
    }


class TestFilterByAge(unittest.TestCase):
    """T3.1 — _filter_by_age helper."""

    def setUp(self):
        self.client = MagicMock()
        self.jikan = MagicMock()
        self.cache = MagicMock()
        self.service = MangaService(self.client, self.jikan, self.cache)

    def test_filter_by_age_guest(self):
        manga_list = [
            {"id": "1", "contentRating": "safe", "demographic": "shounen"},
            {"id": "2", "contentRating": "suggestive", "demographic": "shounen"},
            {"id": "3", "contentRating": None, "demographic": "shounen"},
            {"id": "4", "contentRating": "safe", "demographic": None},  # doujinshi
        ]
        result = self.service._filter_by_age(manga_list, None)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "1")
        self.assertEqual(result[1]["id"], "3")

    def test_filter_by_age_16(self):
        manga_list = [
            {"id": "1", "contentRating": "safe", "demographic": "shounen"},
            {"id": "2", "contentRating": "suggestive", "demographic": "shounen"},
            {"id": "3", "contentRating": None, "demographic": "shounen"},
            {"id": "4", "contentRating": "safe", "demographic": None},  # doujinshi
        ]
        result = self.service._filter_by_age(manga_list, 16)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["id"], "1")
        self.assertEqual(result[1]["id"], "2")
        self.assertEqual(result[2]["id"], "3")

    def test_filter_by_age_18_with_doujinshi(self):
        manga_list = [
            {"id": "1", "contentRating": "safe", "demographic": "shounen"},
            {
                "id": "2",
                "contentRating": "suggestive",
                "demographic": None,
            },  # doujinshi
            {
                "id": "3",
                "contentRating": "erotica",
                "demographic": None,
            },  # doujinshi 18+
        ]
        result = self.service._filter_by_age(manga_list, 18)
        self.assertEqual(len(result), 3)

    def test_filter_by_age_12(self):
        manga_list = [
            {"id": "1", "contentRating": "safe", "demographic": "shounen"},
            {"id": "2", "contentRating": "suggestive", "demographic": "shounen"},
        ]
        result = self.service._filter_by_age(manga_list, 12)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "1")

    def test_filter_by_age_empty_list(self):
        result = self.service._filter_by_age([], 16)
        self.assertEqual(result, [])

    def test_filter_by_age_erotica_guest(self):
        manga_list = [
            {"id": "1", "contentRating": "erotica", "demographic": "shounen"},
        ]
        result = self.service._filter_by_age(manga_list, None)
        self.assertEqual(len(result), 0)

    def test_filter_by_age_erotica_18(self):
        manga_list = [
            {"id": "1", "contentRating": "erotica", "demographic": "shounen"},
        ]
        result = self.service._filter_by_age(manga_list, 18)
        self.assertEqual(len(result), 1)

    def test_filter_by_age_erotica_17(self):
        manga_list = [
            {"id": "1", "contentRating": "erotica", "demographic": "shounen"},
        ]
        result = self.service._filter_by_age(manga_list, 17)
        self.assertEqual(len(result), 0)


class TestSearchByAge(unittest.IsolatedAsyncioTestCase):
    """T3.2 — search() with user_age parameter."""

    def setUp(self):
        self.client = MagicMock()
        self.client.search_manga = AsyncMock()
        self.client.get_statistics = AsyncMock(return_value={"statistics": {}})
        self.jikan = MagicMock()
        self.cache = MagicMock()
        self.cache.get.return_value = None
        self.service = MangaService(self.client, self.jikan, self.cache)

    async def test_search_backward_compat_no_age(self):
        """search without user_age defaults to guest — only safe returned."""
        raw_items = [
            _raw_mangadex_item("1", "safe"),
            _raw_mangadex_item("2", "suggestive"),
        ]
        self.client.search_manga.return_value = {"data": raw_items, "total": 2}

        result = await self.service.search("test")
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["id"], "1")
        self.assertEqual(result["limit"], 10)
        self.assertEqual(result["offset"], 0)
        self.assertEqual(result["total"], 2)

    async def test_search_filters_by_age_12(self):
        """A 12-year-old only sees safe manga."""
        raw_items = [
            _raw_mangadex_item("1", "safe"),
            _raw_mangadex_item("2", "suggestive"),
        ]
        self.client.search_manga.return_value = {"data": raw_items, "total": 2}

        result = await self.service.search("test", user_age=12)
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["id"], "1")

    async def test_search_filters_by_age_16(self):
        """A 16-year-old sees safe + suggestive."""
        raw_items = [
            _raw_mangadex_item("1", "safe"),
            _raw_mangadex_item("2", "suggestive"),
        ]
        self.client.search_manga.return_value = {"data": raw_items, "total": 2}

        result = await self.service.search("test", user_age=16)
        self.assertEqual(len(result["data"]), 2)

    async def test_search_guest_filters_suggestive(self):
        """Guest (user_age=None) sees only safe."""
        raw_items = [
            _raw_mangadex_item("1", "safe"),
            _raw_mangadex_item("2", "suggestive"),
        ]
        self.client.search_manga.return_value = {"data": raw_items, "total": 2}

        result = await self.service.search("test", user_age=None)
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["id"], "1")

    async def test_search_guest_filters_doujinshi(self):
        """Guest (user_age=None) does NOT see content without demographic."""
        raw_items = [
            _raw_mangadex_item("1", "safe", "shounen"),
            _raw_mangadex_item("2", "safe", None),  # doujinshi
        ]
        self.client.search_manga.return_value = {"data": raw_items, "total": 2}

        result = await self.service.search("test", user_age=None)
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["id"], "1")

    async def test_search_18_sees_doujinshi(self):
        """User 18+ sees doujinshi content."""
        raw_items = [
            _raw_mangadex_item("1", "safe", "shounen"),
            _raw_mangadex_item("2", "safe", None),  # doujinshi
        ]
        self.client.search_manga.return_value = {"data": raw_items, "total": 2}

        result = await self.service.search("test", user_age=18)
        self.assertEqual(len(result["data"]), 2)

    async def test_search_forwards_limit_offset_to_client(self):
        """search forwards explicit limit/offset to MangaDex client."""
        raw_items = [
            _raw_mangadex_item("1", "safe"),
            _raw_mangadex_item("3", "suggestive"),
        ]
        self.client.search_manga.return_value = {"data": raw_items, "total": 50}

        result = await self.service.search("test", limit=2, offset=4)

        self.client.search_manga.assert_awaited_once_with(
            query="test", limit=2, offset=4, content_ratings=["safe"]
        )
        self.assertEqual(result["limit"], 2)
        self.assertEqual(result["offset"], 4)
        self.assertEqual(result["total"], 50)


class TestListMangaByAge(unittest.IsolatedAsyncioTestCase):
    """T3.3 — list_manga() with user_age parameter."""

    def setUp(self):
        self.client = MagicMock()
        self.client.list_manga = AsyncMock()
        self.client.get_statistics = AsyncMock(return_value={"statistics": {}})
        self.jikan = MagicMock()
        self.cache = MagicMock()
        self.cache.get.return_value = None
        self.service = MangaService(self.client, self.jikan, self.cache)

    async def test_list_manga_backward_compat_no_age(self):
        """list_manga without user_age defaults to guest — only safe returned."""
        raw_items = [
            _raw_mangadex_item("1", "safe"),
            _raw_mangadex_item("2", "suggestive"),
        ]
        self.client.list_manga.return_value = {
            "data": raw_items,
            "total": 2,
        }

        result = await self.service.list_manga()
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["id"], "1")
        self.assertEqual(result["total"], 2)

    async def test_list_manga_filters_by_age_12(self):
        raw_items = [
            _raw_mangadex_item("1", "safe"),
            _raw_mangadex_item("2", "suggestive"),
        ]
        self.client.list_manga.return_value = {
            "data": raw_items,
            "total": 2,
        }

        result = await self.service.list_manga(user_age=12)
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["id"], "1")
        # total reflects the upstream dataset size, not the filtered page
        self.assertEqual(result["total"], 2)

    async def test_list_manga_filters_by_age_16(self):
        raw_items = [
            _raw_mangadex_item("1", "safe"),
            _raw_mangadex_item("2", "suggestive"),
        ]
        self.client.list_manga.return_value = {
            "data": raw_items,
            "total": 2,
        }

        result = await self.service.list_manga(user_age=16)
        self.assertEqual(len(result["data"]), 2)

    async def test_list_manga_guest_sees_only_safe(self):
        raw_items = [
            _raw_mangadex_item("1", "safe"),
            _raw_mangadex_item("2", "suggestive"),
            _raw_mangadex_item("3", None),
        ]
        self.client.list_manga.return_value = {
            "data": raw_items,
            "total": 3,
        }

        # safe + None (no rating = allowed) pass; suggestive blocked; all have demographic
        result = await self.service.list_manga(user_age=None)
        self.assertEqual(len(result["data"]), 2)
        self.assertEqual(result["total"], 3)


class TestGetByIdByAge(unittest.IsolatedAsyncioTestCase):
    """T3.4 — get_by_id() with user_age parameter."""

    def setUp(self):
        self.client = MagicMock()
        self.client.get_manga = AsyncMock()
        self.jikan = MagicMock()
        self.cache = MagicMock()
        self.cache.get.return_value = None
        self.service = MangaService(self.client, self.jikan, self.cache)

    @patch("app.services.manga_service.settings")
    async def test_get_by_id_returns_none_for_restricted(self, mock_settings):
        """12-year-old cannot access suggestive manga."""
        mock_settings.enable_jikan_enrichment = False
        raw_item = _raw_mangadex_item("1", "suggestive")
        self.client.get_manga.return_value = {"data": raw_item}

        result = await self.service.get_by_id("1", user_age=12)
        self.assertIsNone(result)

    @patch("app.services.manga_service.settings")
    async def test_get_by_id_returns_manga_when_allowed(self, mock_settings):
        """16-year-old can access suggestive manga."""
        mock_settings.enable_jikan_enrichment = False
        raw_item = _raw_mangadex_item("1", "suggestive")
        self.client.get_manga.return_value = {"data": raw_item}

        result = await self.service.get_by_id("1", user_age=16)
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "1")

    @patch("app.services.manga_service.settings")
    async def test_get_by_id_safe_always_allowed(self, mock_settings):
        """Safe manga is accessible regardless of age."""
        mock_settings.enable_jikan_enrichment = False
        raw_item = _raw_mangadex_item("1", "safe")
        self.client.get_manga.return_value = {"data": raw_item}

        result = await self.service.get_by_id("1", user_age=12)
        self.assertIsNotNone(result)

    @patch("app.services.manga_service.settings")
    async def test_get_by_id_backward_compat_no_age(self, mock_settings):
        """get_by_id without user_age defaults to guest — suggestive is blocked."""
        mock_settings.enable_jikan_enrichment = False
        raw_item = _raw_mangadex_item("1", "suggestive")
        self.client.get_manga.return_value = {"data": raw_item}

        result = await self.service.get_by_id("1")
        self.assertIsNone(result)

    @patch("app.services.manga_service.settings")
    async def test_get_by_id_guest_blocks_suggestive(self, mock_settings):
        """Guest (user_age=None) cannot access suggestive."""
        mock_settings.enable_jikan_enrichment = False
        raw_item = _raw_mangadex_item("1", "suggestive")
        self.client.get_manga.return_value = {"data": raw_item}

        result = await self.service.get_by_id("1", user_age=None)
        self.assertIsNone(result)

    @patch("app.services.manga_service.settings")
    async def test_get_by_id_guest_blocks_unrated(self, mock_settings):
        """Guest (user_age=None) cannot access unrated manga (contentRating=None)."""
        mock_settings.enable_jikan_enrichment = False
        raw_item = _raw_mangadex_item("1", None)
        self.client.get_manga.return_value = {"data": raw_item}

        result = await self.service.get_by_id("1", user_age=None)
        self.assertIsNone(result)

    @patch("app.services.manga_service.settings")
    async def test_get_by_id_guest_allows_safe(self, mock_settings):
        """Guest (user_age=None) can access safe manga."""
        mock_settings.enable_jikan_enrichment = False
        raw_item = _raw_mangadex_item("1", "safe")
        self.client.get_manga.return_value = {"data": raw_item}

        result = await self.service.get_by_id("1", user_age=None)
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "1")


if __name__ == "__main__":
    unittest.main()
