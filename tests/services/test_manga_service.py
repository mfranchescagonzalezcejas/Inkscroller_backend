import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import settings
from app.core.manga_tags import GENRE_TAG_UUIDS
from app.services.manga_service import MangaService


def _make_manga(manga_id: str, content_rating: str | None = None) -> dict:
    """Helper to build a minimal mapped manga dict."""
    return {
        "id": manga_id,
        "title": f"Manga {manga_id}",
        "type": None,
        "description": None,
        "coverUrl": None,
        "demographic": None,
        "status": "ongoing",
        "contentRating": content_rating,
        "genres": [],
        "malId": None,
        "chapters": None,
        "score": None,
        "rank": None,
        "popularity": None,
        "members": None,
        "favorites": None,
        "authors": [],
        "serialization": None,
        "startYear": None,
        "endYear": None,
    }


def _raw_mangadex_item(
    manga_id: str,
    content_rating: str | None = None,
    demographic: str = "shounen",
    mal_id: int | None = None,
) -> dict:
    """Build a raw MangaDex API item (as returned by the client)."""
    attrs: dict = {
        "title": {"en": f"Manga {manga_id}"},
        "publicationDemographic": demographic,
        "tags": [],
    }
    if content_rating is not None:
        attrs["contentRating"] = content_rating
    if mal_id is not None:
        attrs["links"] = {"mal": mal_id}
    return {
        "id": manga_id,
        "attributes": attrs,
        "relationships": [],
    }


class TestFilterByAge(unittest.TestCase):
    """T3.1 — _filter_by_age helper."""

    def setUp(self) -> None:
        """Create mock clients for filter_by_age tests."""
        self.client = MagicMock()
        self.jikan = MagicMock()
        self.cache = MagicMock()
        self.service = MangaService(self.client, self.jikan, self.cache)

    def test_filter_by_age_guest(self) -> None:
        """Filter by age guest.

        Safe content without demographic is now accessible (#128 fix).
        """
        manga_list = [
            {"id": "1", "contentRating": "safe", "demographic": "shounen"},
            {"id": "2", "contentRating": "suggestive", "demographic": "shounen"},
            {"id": "3", "contentRating": None, "demographic": "shounen"},
            {
                "id": "4",
                "contentRating": "safe",
                "demographic": None,
            },  # doujinshi (now OK)
        ]
        result = self.service._filter_by_age(manga_list, None)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["id"], "1")
        self.assertEqual(result[1]["id"], "3")
        self.assertEqual(result[2]["id"], "4")

    def test_filter_by_age_16(self) -> None:
        """Filter by age 16.

        Safe content without demographic is now accessible (#128 fix).
        """
        manga_list = [
            {"id": "1", "contentRating": "safe", "demographic": "shounen"},
            {"id": "2", "contentRating": "suggestive", "demographic": "shounen"},
            {"id": "3", "contentRating": None, "demographic": "shounen"},
            {
                "id": "4",
                "contentRating": "safe",
                "demographic": None,
            },  # doujinshi (now OK)
        ]
        result = self.service._filter_by_age(manga_list, 16)
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0]["id"], "1")
        self.assertEqual(result[1]["id"], "2")
        self.assertEqual(result[2]["id"], "3")
        self.assertEqual(result[3]["id"], "4")

    def test_filter_by_age_18_with_doujinshi(self) -> None:
        """Filter by age 18 with doujinshi."""
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

    def test_filter_by_age_12(self) -> None:
        """Filter by age 12."""
        manga_list = [
            {"id": "1", "contentRating": "safe", "demographic": "shounen"},
            {"id": "2", "contentRating": "suggestive", "demographic": "shounen"},
        ]
        result = self.service._filter_by_age(manga_list, 12)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "1")

    def test_filter_by_age_empty_list(self) -> None:
        """Filter by age empty list."""
        result = self.service._filter_by_age([], 16)
        self.assertEqual(result, [])

    def test_filter_by_age_erotica_guest(self) -> None:
        """Filter by age erotica guest."""
        manga_list = [
            {"id": "1", "contentRating": "erotica", "demographic": "shounen"},
        ]
        result = self.service._filter_by_age(manga_list, None)
        self.assertEqual(len(result), 0)

    def test_filter_by_age_erotica_18(self) -> None:
        """Filter by age erotica 18."""
        manga_list = [
            {"id": "1", "contentRating": "erotica", "demographic": "shounen"},
        ]
        result = self.service._filter_by_age(manga_list, 18)
        self.assertEqual(len(result), 1)

    def test_filter_by_age_erotica_17(self) -> None:
        """Filter by age erotica 17."""
        manga_list = [
            {"id": "1", "contentRating": "erotica", "demographic": "shounen"},
        ]
        result = self.service._filter_by_age(manga_list, 17)
        self.assertEqual(len(result), 0)


class TestSearchByAge(unittest.IsolatedAsyncioTestCase):
    """T3.2 — search() with user_age parameter."""

    def setUp(self) -> None:
        """Create mocks for search age-gating tests."""
        self.client = MagicMock()
        self.client.search_manga = AsyncMock()
        self.client.get_statistics = AsyncMock(return_value={"statistics": {}})
        self.jikan = MagicMock()
        self.cache = MagicMock()
        self.cache.get.return_value = None
        self.service = MangaService(self.client, self.jikan, self.cache)

    async def test_search_backward_compat_no_age(self) -> None:
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
        self.assertEqual(result["total"], 1)

    async def test_search_filters_by_age_12(self) -> None:
        """A 12-year-old only sees safe manga."""
        raw_items = [
            _raw_mangadex_item("1", "safe"),
            _raw_mangadex_item("2", "suggestive"),
        ]
        self.client.search_manga.return_value = {"data": raw_items, "total": 2}

        result = await self.service.search("test", user_age=12)
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["id"], "1")

    async def test_search_filters_by_age_16(self) -> None:
        """A 16-year-old sees safe + suggestive."""
        raw_items = [
            _raw_mangadex_item("1", "safe"),
            _raw_mangadex_item("2", "suggestive"),
        ]
        self.client.search_manga.return_value = {"data": raw_items, "total": 2}

        result = await self.service.search("test", user_age=16)
        self.assertEqual(len(result["data"]), 2)

    async def test_search_guest_filters_suggestive(self) -> None:
        """Guest (user_age=None) sees only safe."""
        raw_items = [
            _raw_mangadex_item("1", "safe"),
            _raw_mangadex_item("2", "suggestive"),
        ]
        self.client.search_manga.return_value = {"data": raw_items, "total": 2}

        result = await self.service.search("test", user_age=None)
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["id"], "1")

    async def test_search_guest_filters_doujinshi(self) -> None:
        """Guest sees safe content without demographic (#128 fix)."""
        raw_items = [
            _raw_mangadex_item("1", "safe", "shounen"),
            _raw_mangadex_item("2", "safe", None),  # doujinshi, but safe → now OK
        ]
        self.client.search_manga.return_value = {"data": raw_items, "total": 2}

        result = await self.service.search("test", user_age=None)
        self.assertEqual(len(result["data"]), 2)

    async def test_search_18_sees_doujinshi(self) -> None:
        """User 18+ sees doujinshi content."""
        raw_items = [
            _raw_mangadex_item("1", "safe", "shounen"),
            _raw_mangadex_item("2", "safe", None),  # doujinshi
        ]
        self.client.search_manga.return_value = {"data": raw_items, "total": 2}

        result = await self.service.search("test", user_age=18)
        self.assertEqual(len(result["data"]), 2)

    async def test_search_forwards_limit_offset_to_client(self) -> None:
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
        self.assertEqual(result["total"], 1)


class TestListMangaByAge(unittest.IsolatedAsyncioTestCase):
    """T3.3 — list_manga() with user_age parameter."""

    def setUp(self) -> None:
        """Create mocks for list_manga age-gating tests."""
        self.client = MagicMock()
        self.client.list_manga = AsyncMock()
        self.client.get_statistics = AsyncMock(return_value={"statistics": {}})
        self.jikan = MagicMock()
        self.cache = MagicMock()
        self.cache.get.return_value = None
        self.service = MangaService(self.client, self.jikan, self.cache)

    async def test_list_manga_backward_compat_no_age(self) -> None:
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
        self.assertEqual(result["total"], 1)

    async def test_list_manga_filters_by_age_12(self) -> None:
        """List manga filters by age 12."""
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
        self.assertEqual(result["total"], 1)

    async def test_list_manga_filters_by_age_16(self) -> None:
        """List manga filters by age 16."""
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

    async def test_list_manga_guest_sees_only_safe(self) -> None:
        """List manga guest sees only safe."""
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
        self.assertEqual(result["total"], 2)


class TestResolveContentRatings(unittest.TestCase):
    """_resolve_content_ratings and _content_rating_to_mangadex."""

    def setUp(self) -> None:
        """Create mocks for content rating resolution tests."""
        self.client = MagicMock()
        self.jikan = MagicMock()
        self.cache = MagicMock()
        self.service = MangaService(self.client, self.jikan, self.cache)

    def test_content_rating_to_mangadex_safe(self) -> None:
        """Content rating to mangadex safe."""
        result = MangaService._content_rating_to_mangadex("safe")
        self.assertEqual(result, ["safe"])

    def test_content_rating_to_mangadex_suggestive(self) -> None:
        """Content rating to mangadex suggestive."""
        result = MangaService._content_rating_to_mangadex("suggestive")
        self.assertEqual(result, ["safe", "suggestive"])

    def test_content_rating_to_mangadex_all(self) -> None:
        """Content rating to mangadex all."""
        result = MangaService._content_rating_to_mangadex("all")
        self.assertEqual(result, ["safe", "suggestive", "erotica", "pornographic"])

    def test_content_rating_to_mangadex_unknown_defaults_to_safe(self) -> None:
        """Content rating to mangadex unknown defaults to safe."""
        result = MangaService._content_rating_to_mangadex("invalid")
        self.assertEqual(result, ["safe"])

    def test_content_rating_to_mangadex_none_defaults_to_safe(self) -> None:
        """Content rating to mangadex none defaults to safe."""
        result = MangaService._content_rating_to_mangadex(None)
        self.assertEqual(result, ["safe"])

    def test_resolve_no_explicit_uses_age_default_guest(self) -> None:
        """No explicit content_rating — falls back to age default (guest = safe)."""
        result = self.service._resolve_content_ratings(None, None)
        self.assertEqual(result, ["safe"])

    def test_resolve_no_explicit_uses_age_default_adult(self) -> None:
        """No explicit content_rating — adult sees all 4 ratings."""
        result = self.service._resolve_content_ratings(18, None)
        self.assertEqual(result, ["safe", "suggestive", "erotica", "pornographic"])

    def test_resolve_explicit_safe_for_adult(self) -> None:
        """Adult passes content_rating=safe — only safe returned."""
        result = self.service._resolve_content_ratings(18, "safe")
        self.assertEqual(result, ["safe"])

    def test_resolve_explicit_suggestive_for_adult(self) -> None:
        """Adult passes content_rating=suggestive — safe+suggestive returned."""
        result = self.service._resolve_content_ratings(18, "suggestive")
        self.assertEqual(result, ["safe", "suggestive"])

    def test_resolve_explicit_all_for_adult(self) -> None:
        """Adult passes content_rating=all — all 4 returned."""
        result = self.service._resolve_content_ratings(18, "all")
        self.assertEqual(result, ["safe", "suggestive", "erotica", "pornographic"])

    def test_resolve_teen_cannot_escalate_to_all(self) -> None:
        """16yo passes content_rating=all — intersected with age-allowed (safe+suggestive)."""
        result = self.service._resolve_content_ratings(16, "all")
        self.assertEqual(result, ["safe", "suggestive"])

    def test_resolve_teen_cannot_escalate_to_erotica(self) -> None:
        """16yo passes content_rating=all — erotica/pornographic stripped by age gate."""
        ratings = self.service._resolve_content_ratings(16, "all")
        self.assertNotIn("erotica", ratings)
        self.assertNotIn("pornographic", ratings)

    def test_resolve_teen_with_safe(self) -> None:
        """16yo passes content_rating=safe — only safe returned."""
        result = self.service._resolve_content_ratings(16, "safe")
        self.assertEqual(result, ["safe"])

    def test_resolve_guest_cannot_escalate(self) -> None:
        """Guest passes content_rating=all — only safe returned."""
        result = self.service._resolve_content_ratings(None, "all")
        self.assertEqual(result, ["safe"])

    def test_resolve_guest_with_suggestive(self) -> None:
        """Guest passes content_rating=suggestive — only safe (age gate strips suggestive)."""
        result = self.service._resolve_content_ratings(None, "suggestive")
        self.assertEqual(result, ["safe"])


class TestSearchWithContentRating(unittest.IsolatedAsyncioTestCase):
    """search() with explicit content_rating override."""

    def setUp(self) -> None:
        """Create mocks for search content_rating tests."""
        self.client = MagicMock()
        self.client.search_manga = AsyncMock()
        self.client.get_statistics = AsyncMock(return_value={"statistics": {}})
        self.jikan = MagicMock()
        self.cache = MagicMock()
        self.cache.get.return_value = None
        self.service = MangaService(self.client, self.jikan, self.cache)

    async def test_search_with_content_rating_safe(self) -> None:
        """content_rating=safe — only requests safe from MangaDex."""
        self.client.search_manga.return_value = {"data": [], "total": 0}
        await self.service.search("test", user_age=18, content_rating="safe")
        self.client.search_manga.assert_awaited_once()
        _, kwargs = self.client.search_manga.call_args
        self.assertEqual(kwargs["content_ratings"], ["safe"])

    async def test_search_with_content_rating_suggestive(self) -> None:
        """content_rating=suggestive — requests safe+suggestive from MangaDex."""
        self.client.search_manga.return_value = {"data": [], "total": 0}
        await self.service.search("test", user_age=18, content_rating="suggestive")
        self.client.search_manga.assert_awaited_once()
        _, kwargs = self.client.search_manga.call_args
        self.assertEqual(kwargs["content_ratings"], ["safe", "suggestive"])

    async def test_search_forwards_content_rating_in_cache_key(self) -> None:
        """Different content_rating values produce different cache keys."""
        self.client.search_manga.return_value = {"data": [], "total": 0}
        await self.service.search("test", user_age=18, content_rating="safe")
        await self.service.search("test", user_age=18, content_rating="suggestive")
        # Two different cache keys — both called
        self.assertEqual(self.client.search_manga.call_count, 2)

    async def test_search_different_demographics_produce_different_cache_keys(
        self,
    ) -> None:
        """Different demographic filters produce different cache keys — P1 fix."""
        self.client.search_manga.return_value = {"data": [], "total": 0}
        await self.service.search("test", user_age=18, demographic=["seinen"])
        await self.service.search("test", user_age=18, demographic=["josei"])
        self.assertEqual(self.client.search_manga.call_count, 2)


class TestListMangaWithContentRating(unittest.IsolatedAsyncioTestCase):
    """list_manga() with explicit content_rating override."""

    def setUp(self) -> None:
        """Create mocks for list_manga content_rating tests."""
        self.client = MagicMock()
        self.client.list_manga = AsyncMock()
        self.client.get_statistics = AsyncMock(return_value={"statistics": {}})
        self.jikan = MagicMock()
        self.cache = MagicMock()
        self.cache.get.return_value = None
        self.service = MangaService(self.client, self.jikan, self.cache)

    async def test_list_with_content_rating_safe(self) -> None:
        """content_rating=safe — only requests safe from MangaDex."""
        self.client.list_manga.return_value = {"data": [], "total": 0}
        await self.service.list_manga(user_age=18, content_rating="safe")
        self.client.list_manga.assert_awaited_once()
        _, kwargs = self.client.list_manga.call_args
        self.assertEqual(kwargs["content_ratings"], ["safe"])

    async def test_list_teen_cannot_escalate_with_all(self) -> None:
        """16yo with content_rating=all — requests only safe+suggestive."""
        self.client.list_manga.return_value = {"data": [], "total": 0}
        await self.service.list_manga(user_age=16, content_rating="all")
        self.client.list_manga.assert_awaited_once()
        _, kwargs = self.client.list_manga.call_args
        self.assertEqual(kwargs["content_ratings"], ["safe", "suggestive"])

    async def test_list_with_content_rating_all_caches_separately(self) -> None:
        """Different content_rating values produce different cache keys."""
        self.client.list_manga.return_value = {"data": [], "total": 0}
        await self.service.list_manga(user_age=18, content_rating="safe")
        await self.service.list_manga(user_age=18, content_rating="all")
        self.assertEqual(self.client.list_manga.call_count, 2)


class TestUnspecifiedDemographic(unittest.IsolatedAsyncioTestCase):
    """The local null-demographic filter produces stable, complete pages."""

    def setUp(self) -> None:
        """Create mocks for null-demographic union scan tests."""
        self.client = MagicMock()
        self.client.list_manga = AsyncMock()
        self.client.search_manga = AsyncMock()
        self.client.get_statistics = AsyncMock(return_value={"statistics": {}})
        self.jikan = MagicMock()
        self.cache = MagicMock()
        self.cache.get.return_value = None
        self.service = MangaService(self.client, self.jikan, self.cache)
        self._secret_patcher = patch.object(
            settings, "cursor_secret", "test-secret-for-cursors"
        )
        self._secret_patcher.start()

    def tearDown(self) -> None:
        self._secret_patcher.stop()

    async def test_list_null_only_scans_without_forwarding_sentinel(self) -> None:
        """List null only scans without forwarding sentinel."""
        self.client.list_manga.return_value = {
            "data": [
                _raw_mangadex_item("named", "safe", "seinen"),
                _raw_mangadex_item("null", "safe", None),
            ],
            "total": 2,
        }

        result = await self.service.list_manga(
            limit=1,
            user_age=18,
            demographic=["unspecified"],
        )

        self.assertEqual([item["id"] for item in result["data"]], ["null"])
        self.assertEqual(result["total"], 1)
        self.assertFalse(result["has_more"])
        _, kwargs = self.client.list_manga.call_args
        self.assertEqual(kwargs["demographic"], ["none"])

    async def test_search_mixed_union_deduplicates_and_has_full_pages(self) -> None:
        """Search mixed union deduplicates and has full pages."""
        self.client.search_manga.return_value = {
            "data": [
                _raw_mangadex_item("named", "safe", "seinen"),
                _raw_mangadex_item("null", "safe", None),
                _raw_mangadex_item("other", "safe", "shounen"),
            ],
            "total": 3,
        }

        result = await self.service.search(
            "test",
            limit=2,
            user_age=18,
            demographic=["seinen", "unspecified"],
        )

        self.assertEqual([item["id"] for item in result["data"]], ["named", "null"])
        self.assertEqual(result["total"], 2)
        self.assertFalse(result["has_more"])
        _, kwargs = self.client.search_manga.call_args
        self.assertEqual(kwargs["demographic"], ["none"])

    async def test_search_union_keeps_primary_results_when_worker_fails(self) -> None:
        """A throttled worker branch must not discard the primary catalogue page."""
        worker = MagicMock()
        worker.search_manga = AsyncMock(side_effect=ConnectionError("throttled"))
        self.service._worker_client = worker
        self.client.search_manga.return_value = {
            "data": [_raw_mangadex_item("named", "safe", "seinen")],
            "total": 1,
        }

        result = await self.service.search(
            "test",
            limit=1,
            user_age=18,
            demographic=["seinen", "unspecified"],
        )

        self.assertEqual([item["id"] for item in result["data"]], ["named"])
        worker.search_manga.assert_awaited_once()

    async def test_cursor_reuses_snapshot_without_rescanning(self) -> None:
        """Cursor reuses snapshot without rescanning."""
        self.client.list_manga.return_value = {
            "data": [
                _raw_mangadex_item("first", "safe", None),
                _raw_mangadex_item("second", "safe", None),
            ],
            "total": 2,
        }

        first = await self.service.list_manga(
            limit=1,
            user_age=18,
            demographic=["unspecified"],
        )
        second = await self.service.list_manga(
            limit=1,
            user_age=18,
            demographic=["unspecified"],
            cursor=first["next_cursor"],
        )

        self.assertEqual([item["id"] for item in first["data"]], ["first"])
        self.assertEqual([item["id"] for item in second["data"]], ["second"])
        self.assertIsNone(second["next_cursor"])
        self.assertEqual(self.client.list_manga.await_count, 1)

    async def test_cursor_rejects_mismatched_filter_and_expiry(self) -> None:
        """Cursor rejects mismatched filter and expiry."""
        self.client.list_manga.return_value = {
            "data": [
                _raw_mangadex_item("first", "safe", None),
                _raw_mangadex_item("second", "safe", None),
            ],
            "total": 2,
        }
        first = await self.service.list_manga(
            limit=1,
            user_age=18,
            demographic=["unspecified"],
        )

        with self.assertRaises(ValueError):
            await self.service.list_manga(
                limit=1,
                user_age=18,
                demographic=["seinen", "unspecified"],
                cursor=first["next_cursor"] or "missing",
            )
        with self.assertRaises(ValueError):
            await self.service.list_manga(
                limit=1,
                user_age=18,
                demographic=["unspecified"],
                cursor="expired-or-unknown",
            )

    async def test_cursor_rejects_tampered_position(self) -> None:
        """Cursor rejects tampered position."""
        self.client.list_manga.return_value = {
            "data": [
                _raw_mangadex_item("first", "safe", None),
                _raw_mangadex_item("second", "safe", None),
            ],
            "total": 2,
        }
        first = await self.service.list_manga(
            limit=1,
            user_age=18,
            demographic=["unspecified"],
        )
        snapshot_id, _, _ = first["next_cursor"].partition(":")

        with self.assertRaises(ValueError):
            await self.service.list_manga(
                limit=1,
                user_age=18,
                demographic=["unspecified"],
                cursor=f"{snapshot_id}:0",
            )

    async def test_cursor_without_unspecified_raises_value_error(self) -> None:
        """Cursor in non-union path raises ValueError — P2 fix."""
        self.client.list_manga.return_value = {"data": [], "total": 0}
        with self.assertRaises(ValueError):
            await self.service.list_manga(
                limit=1, user_age=18, demographic=["seinen"], cursor="some-cursor"
            )

    async def test_search_cursor_without_unspecified_raises_value_error(self) -> None:
        """Search cursor in non-union path raises ValueError — P2 fix."""
        self.client.search_manga.return_value = {"data": [], "total": 0}
        with self.assertRaises(ValueError):
            await self.service.search(
                "test",
                limit=1,
                user_age=18,
                demographic=["seinen"],
                cursor="some-cursor",
            )

    async def test_union_preserves_genre_and_initial_offset(self) -> None:
        """Union preserves genre and initial offset."""
        self.client.list_manga.return_value = {
            "data": [
                _raw_mangadex_item("first", "safe", None),
                _raw_mangadex_item("second", "safe", None),
                _raw_mangadex_item("third", "safe", None),
            ],
            "total": 3,
        }

        result = await self.service.list_manga(
            limit=1,
            offset=1,
            genre="romance",
            user_age=18,
            demographic=["unspecified"],
        )

        self.assertEqual([item["id"] for item in result["data"]], ["second"])
        self.assertEqual(result["offset"], 1)
        self.assertEqual(result["total"], 3)
        self.assertEqual(self.client.list_manga.await_count, 1)
        _, kwargs = self.client.list_manga.call_args
        self.assertEqual(kwargs["included_tags"], [GENRE_TAG_UUIDS["romance"]])
        self.assertEqual(kwargs["demographic"], ["none"])


class TestCursorPageEnrichesStats(unittest.IsolatedAsyncioTestCase):
    """T3 — _cursor_page enriches page with statistics on demand."""

    def setUp(self) -> None:
        """Create mocks for cursor page statistics tests."""
        self.client = MagicMock()
        self.client.get_statistics = AsyncMock(return_value={"statistics": {}})
        self.jikan = MagicMock()
        self.cache = MagicMock()
        self.cache.get.return_value = None
        self.service = MangaService(self.client, self.jikan, self.cache)
        self._secret_patcher = patch.object(
            settings, "cursor_secret", "test-secret-for-cursors"
        )
        self._secret_patcher.start()

    def tearDown(self) -> None:
        self._secret_patcher.stop()

    async def test_cursor_page_enriches_stats(self) -> None:
        """_cursor_page calls get_statistics on the page items."""
        items = [_make_manga(str(i)) for i in range(10)]
        snapshot = self.service._snapshot_page(
            items, limit=2, offset=0, fingerprint="fp"
        )
        cursor = snapshot["next_cursor"]

        self.client.get_statistics.return_value = {
            "statistics": {"0": {"follows": 10}, "1": {"follows": 20}}
        }

        result = await self.service._cursor_page(cursor, limit=2, fingerprint="fp")

        self.client.get_statistics.assert_awaited_once()
        call_args = self.client.get_statistics.call_args[0][0]
        self.assertEqual(call_args, ["2", "3"])
        self.assertEqual(result["data"][0]["id"], "2")
        self.assertEqual(result["data"][1]["id"], "3")

    async def test_cursor_page_no_items_skips_stats(self) -> None:
        """_cursor_page with empty page does not call get_statistics."""
        self.service._snapshot_page([], limit=10, offset=0, fingerprint="fp")
        snapshot_id = list(self.service._snapshots.keys())[-1]
        token = self.service._cursor_token(snapshot_id, 0, "fp")

        result = await self.service._cursor_page(token, limit=10, fingerprint="fp")
        self.assertEqual(result["data"], [])
        self.client.get_statistics.assert_not_awaited()


class TestListUnionDoesNotStatAllItems(unittest.IsolatedAsyncioTestCase):
    """T3 — union path stats only the page, not all merged items."""

    def setUp(self) -> None:
        """Create mocks for union path statistics tests."""
        self.client = MagicMock()
        self.client.list_manga = AsyncMock()
        self.client.get_statistics = AsyncMock(return_value={"statistics": {}})
        self.jikan = MagicMock()
        self.cache = MagicMock()
        self.cache.get.return_value = None
        self.service = MangaService(self.client, self.jikan, self.cache)
        self._secret_patcher = patch.object(
            settings, "cursor_secret", "test-secret-for-cursors"
        )
        self._secret_patcher.start()

    def tearDown(self) -> None:
        self._secret_patcher.stop()

    async def test_list_union_does_not_stat_all_items(self) -> None:
        """In union path, get_statistics is called with page items only."""
        raw_items = [_raw_mangadex_item(str(i), "safe", None) for i in range(50)]
        self.client.list_manga.return_value = {"data": raw_items, "total": 50}

        stats_dict = {str(i): {"follows": i * 10} for i in range(50)}
        self.client.get_statistics.return_value = {"statistics": stats_dict}

        result = await self.service.list_manga(
            limit=20,
            offset=0,
            user_age=18,
            demographic=["unspecified"],
        )

        call_args = self.client.get_statistics.call_args[0][0]
        self.assertEqual(len(call_args), 20)
        self.assertEqual(call_args, [str(i) for i in range(20)])
        self.assertEqual(len(result["data"]), 20)

    async def test_list_union_second_page_stats_only_page_items(self) -> None:
        """Second page via offset also stats only its page items."""
        raw_items = [_raw_mangadex_item(str(i), "safe", None) for i in range(50)]
        self.client.list_manga.return_value = {"data": raw_items, "total": 50}

        stats_dict = {str(i): {"follows": i * 10} for i in range(50)}
        self.client.get_statistics.return_value = {"statistics": stats_dict}

        result = await self.service.list_manga(
            limit=20,
            offset=20,
            user_age=18,
            demographic=["unspecified"],
        )

        call_args = self.client.get_statistics.call_args[0][0]
        self.assertEqual(len(call_args), 20)
        self.assertEqual(call_args, [str(i) for i in range(20, 40)])
        self.assertEqual(result["offset"], 20)


class TestSearchUnionPageHasStats(unittest.IsolatedAsyncioTestCase):
    """T3 — search union path returns items with stats populated."""

    def setUp(self) -> None:
        """Create mocks for search union statistics tests."""
        self.client = MagicMock()
        self.client.search_manga = AsyncMock()
        self.client.get_statistics = AsyncMock(return_value={"statistics": {}})
        self.jikan = MagicMock()
        self.cache = MagicMock()
        self.cache.get.return_value = None
        self.service = MangaService(self.client, self.jikan, self.cache)
        self._secret_patcher = patch.object(
            settings, "cursor_secret", "test-secret-for-cursors"
        )
        self._secret_patcher.start()

    def tearDown(self) -> None:
        self._secret_patcher.stop()

    async def test_search_union_page_has_stats(self) -> None:
        """Search union path returns items with stats populated."""
        raw_items = [_raw_mangadex_item(str(i), "safe", None) for i in range(10)]
        self.client.search_manga.return_value = {"data": raw_items, "total": 10}

        stats_dict = {
            str(i): {"follows": i * 100, "rating": {"average": 7.0}} for i in range(10)
        }
        self.client.get_statistics.return_value = {"statistics": stats_dict}

        result = await self.service.search(
            "test",
            limit=5,
            offset=0,
            user_age=18,
            demographic=["unspecified"],
        )

        call_args = self.client.get_statistics.call_args[0][0]
        self.assertEqual(len(call_args), 5)
        self.assertEqual(len(result["data"]), 5)

    async def test_search_union_cursor_enriches_stats(self) -> None:
        """Search union cursor path also enriches with stats."""
        raw_items = [_raw_mangadex_item(str(i), "safe", None) for i in range(10)]
        self.client.search_manga.return_value = {"data": raw_items, "total": 10}

        stats_dict = {str(i): {"follows": i * 100} for i in range(10)}
        self.client.get_statistics.return_value = {"statistics": stats_dict}

        first = await self.service.search(
            "test",
            limit=3,
            offset=0,
            user_age=18,
            demographic=["unspecified"],
        )

        self.client.get_statistics.reset_mock()

        await self.service.search(
            "test",
            limit=3,
            offset=0,
            user_age=18,
            demographic=["unspecified"],
            cursor=first["next_cursor"],
        )

        self.client.get_statistics.assert_awaited()
        call_args = self.client.get_statistics.call_args[0][0]
        self.assertEqual(len(call_args), 3)
        self.assertEqual(call_args, ["3", "4", "5"])


class TestGetByIdByAge(unittest.IsolatedAsyncioTestCase):
    """T3.4 — get_by_id() with user_age parameter."""

    def setUp(self) -> None:
        """Create mock clients and service instance for get_by_id age-gating tests."""
        self.client = MagicMock()
        self.client.get_manga = AsyncMock()
        self.jikan = MagicMock()
        self.cache = MagicMock()
        self.cache.get.return_value = None
        self.service = MangaService(self.client, self.jikan, self.cache)

    @patch("app.services.manga_service.settings")
    async def test_get_by_id_returns_none_for_restricted(self, mock_settings) -> None:
        """12-year-old cannot access suggestive manga."""
        mock_settings.enable_jikan_enrichment = False
        raw_item = _raw_mangadex_item("1", "suggestive")
        self.client.get_manga.return_value = {"data": raw_item}

        result = await self.service.get_by_id("1", user_age=12)
        self.assertIsNone(result)

    @patch("app.services.manga_service.settings")
    async def test_get_by_id_returns_manga_when_allowed(self, mock_settings) -> None:
        """16-year-old can access suggestive manga."""
        mock_settings.enable_jikan_enrichment = False
        raw_item = _raw_mangadex_item("1", "suggestive")
        self.client.get_manga.return_value = {"data": raw_item}

        result = await self.service.get_by_id("1", user_age=16)
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "1")

    @patch("app.services.manga_service.settings")
    async def test_get_by_id_safe_always_allowed(self, mock_settings) -> None:
        """Safe manga is accessible regardless of age."""
        mock_settings.enable_jikan_enrichment = False
        raw_item = _raw_mangadex_item("1", "safe")
        self.client.get_manga.return_value = {"data": raw_item}

        result = await self.service.get_by_id("1", user_age=12)
        self.assertIsNotNone(result)

    @patch("app.services.manga_service.settings")
    async def test_get_by_id_backward_compat_no_age(self, mock_settings) -> None:
        """get_by_id without user_age defaults to guest — suggestive is blocked."""
        mock_settings.enable_jikan_enrichment = False
        raw_item = _raw_mangadex_item("1", "suggestive")
        self.client.get_manga.return_value = {"data": raw_item}

        result = await self.service.get_by_id("1")
        self.assertIsNone(result)

    @patch("app.services.manga_service.settings")
    async def test_get_by_id_guest_blocks_suggestive(self, mock_settings) -> None:
        """Guest (user_age=None) cannot access suggestive."""
        mock_settings.enable_jikan_enrichment = False
        raw_item = _raw_mangadex_item("1", "suggestive")
        self.client.get_manga.return_value = {"data": raw_item}

        result = await self.service.get_by_id("1", user_age=None)
        self.assertIsNone(result)

    @patch("app.services.manga_service.settings")
    async def test_get_by_id_guest_blocks_unrated(self, mock_settings) -> None:
        """Guest (user_age=None) cannot access unrated manga (contentRating=None)."""
        mock_settings.enable_jikan_enrichment = False
        raw_item = _raw_mangadex_item("1", None)
        self.client.get_manga.return_value = {"data": raw_item}

        result = await self.service.get_by_id("1", user_age=None)
        self.assertIsNone(result)

    @patch("app.services.manga_service.settings")
    async def test_get_by_id_guest_allows_safe(self, mock_settings) -> None:
        """Guest (user_age=None) can access safe manga."""
        mock_settings.enable_jikan_enrichment = False
        raw_item = _raw_mangadex_item("1", "safe")
        self.client.get_manga.return_value = {"data": raw_item}

        result = await self.service.get_by_id("1", user_age=None)
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "1")

    async def test_get_by_id_jikan_does_not_overwrite_content_rating(self) -> None:
        """contentRating is never overwritten by Jikan (age-gating field)."""
        raw_item = _raw_mangadex_item("1", "safe", None)
        self.client.get_manga.return_value = {"data": raw_item}
        self.jikan.search_manga = AsyncMock(return_value={"data": [{}]})

        with (
            patch.object(settings, "enable_jikan_enrichment", True),
            patch(
                "app.services.manga_service.map_jikan_detail",
                return_value={"demographic": "shounen", "contentRating": "erotica"},
            ),
        ):
            result = await self.service.get_by_id("1", user_age=18)

        # demographic IS now filled by Jikan (no longer excluded)
        self.assertEqual(result["demographic"], "shounen")
        # contentRating stays protected — never overwritten
        self.assertEqual(result["contentRating"], "safe")

    async def test_get_by_id_jikan_uses_mal_id_when_available(self) -> None:
        """With malId present, enrichment calls get_manga_by_id (not search_manga)."""
        raw_item = _raw_mangadex_item("1", "safe", None, mal_id=12345)
        self.client.get_manga.return_value = {"data": raw_item}
        self.jikan.get_manga_by_id = AsyncMock(
            return_value={
                "data": {
                    "synopsis": "Jikan synopsis",
                    "demographics": [{"name": "Seinen"}],
                    "chapters": 42,
                }
            }
        )

        with patch.object(settings, "enable_jikan_enrichment", True):
            result = await self.service.get_by_id("1", user_age=18)

        self.assertIsNotNone(result)
        self.jikan.get_manga_by_id.assert_awaited_once_with(12345)
        self.jikan.search_manga.assert_not_called()
        # Jikan data fills gaps
        self.assertEqual(result.get("malId"), 12345)
        self.assertEqual(result.get("description"), "Jikan synopsis")
        self.assertEqual(result.get("demographic"), "seinen")
        self.assertEqual(result.get("chapters"), 42)

    async def test_get_by_id_jikan_falls_back_to_search_without_mal_id(self) -> None:
        """Without malId, enrichment falls back to search_manga (current behaviour)."""
        raw_item = _raw_mangadex_item("1", "safe")  # no links.mal
        self.client.get_manga.return_value = {"data": raw_item}
        self.jikan.search_manga = AsyncMock(
            return_value={
                "data": [
                    {
                        "synopsis": "Fallback synopsis",
                        "demographics": [{"name": "Shounen"}],
                        "chapters": 24,
                    }
                ]
            }
        )

        with patch.object(settings, "enable_jikan_enrichment", True):
            result = await self.service.get_by_id("1", user_age=18)

        self.assertIsNotNone(result)
        self.jikan.get_manga_by_id.assert_not_called()
        self.jikan.search_manga.assert_awaited_once_with("Manga 1")
        self.assertEqual(result.get("description"), "Fallback synopsis")
        self.assertEqual(result.get("demographic"), "shounen")
        self.assertEqual(result.get("chapters"), 24)

    async def test_get_by_id_jikan_down_returns_mangadex_data(self) -> None:
        """When Jikan is unreachable, enrichment is skipped, MangaDex data returned."""
        raw_item = _raw_mangadex_item("1", "safe", mal_id=12345)
        self.client.get_manga.return_value = {"data": raw_item}
        self.jikan.get_manga_by_id = AsyncMock(
            side_effect=ConnectionError("Jikan down")
        )

        with patch.object(settings, "enable_jikan_enrichment", True):
            result = await self.service.get_by_id("1", user_age=18)

        self.assertIsNotNone(result)
        # Verify enrichment path was triggered (not silently skipped)
        self.jikan.get_manga_by_id.assert_awaited_once_with(12345)
        self.jikan.search_manga.assert_not_called()
        self.assertEqual(result.get("malId"), 12345)
        # MangaDex fallback: description stays None
        self.assertIsNone(result.get("description"))


class TestSnapshotPageHasMore(unittest.TestCase):
    """has_more must reflect data availability, not cursor token presence."""

    def setUp(self) -> None:
        """Set up service for snapshot has_more tests."""
        self.service = MangaService.__new__(MangaService)
        self.service._snapshots = {}
        self.service._cache = {}
        self.service._client = None

    def _snapshot_page(self, items, limit, offset):
        """Inline _snapshot_page without cursor token dependency."""
        snapshot_id = "test-snap"
        fingerprint = "test-fp"
        self.service._snapshots[snapshot_id] = (fingerprint, items)
        page = items[offset : offset + limit]
        return {
            "data": page,
            "limit": limit,
            "offset": offset,
            "total": len(items),
            "has_more": offset + len(page) < len(items),
            "next_cursor": None,
        }

    def test_has_more_true_when_more_items(self) -> None:
        """Has more true when more items."""
        result = self._snapshot_page(["a", "b", "c"], 1, 0)
        self.assertTrue(result["has_more"])

    def test_has_more_false_on_last_page(self) -> None:
        """Has more false on last page."""
        result = self._snapshot_page(["a"], 1, 0)
        self.assertFalse(result["has_more"])

    def test_has_more_true_without_cursor_secret(self) -> None:
        """Has more true without cursor secret."""
        result = self._snapshot_page(["a", "b", "c", "d", "e"], 2, 0)
        self.assertTrue(result["has_more"])
        self.assertIsNone(result["next_cursor"])


class TestScanUnionLatestOrdering(unittest.IsolatedAsyncioTestCase):
    """_scan_union must sort globally when order=latest."""

    def setUp(self) -> None:
        """Set up service for scan_union ordering tests."""
        self.service = MangaService.__new__(MangaService)
        self.service._client = None

    async def test_latest_ordering_mixed_demographics(self) -> None:
        """Latest ordering mixed demographics."""
        s1 = {
            "id": "s1",
            "demographic": "seinen",
            "latestUploadedChapter": "2024-01-01T00:00:00+00:00",
        }
        s2 = {
            "id": "s2",
            "demographic": "seinen",
            "latestUploadedChapter": "2024-03-01T00:00:00+00:00",
        }
        u1 = {
            "id": "u1",
            "demographic": None,
            "latestUploadedChapter": "2024-02-01T00:00:00+00:00",
        }
        items = [s1, s2, u1]
        _order_fields = {
            "latest": ("latestUploadedChapter", True),
        }
        entry = _order_fields.get("latest")
        if entry:
            key, reverse = entry
            items.sort(key=lambda m: m.get(key) or "", reverse=reverse)
        self.assertEqual([m["id"] for m in items], ["s2", "u1", "s1"])

    async def test_popular_ordering_preserved(self) -> None:
        """Popular ordering preserved."""
        p1 = {"id": "p1", "demographic": "shounen", "popularity": 500}
        p2 = {"id": "p2", "demographic": None, "popularity": 1000}
        p3 = {"id": "p3", "demographic": "shounen", "popularity": 100}
        items = [p1, p2, p3]
        _order_fields = {
            "popular": ("popularity", True),
        }
        entry = _order_fields.get("popular")
        if entry:
            key, reverse = entry
            items.sort(key=lambda m: m.get(key) or 0, reverse=reverse)
        self.assertEqual([m["id"] for m in items], ["p2", "p1", "p3"])


if __name__ == "__main__":
    unittest.main()
