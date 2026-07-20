"""Tests for the tags backend service: client, service, cache, fallback, and route."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.cache import SimpleCache
from app.core.dependencies import get_tag_service
from app.core.manga_tags import GENRE_TAG_UUIDS
from app.services.tag_service import TagService
from app.sources.mangadex_client import MangaDexClient
from tests.api.helpers import create_hermetic_test_app


class TestMangaDexClientGetTags(unittest.IsolatedAsyncioTestCase):
    """T1.1 — MangaDexClient.get_tags() retrying upstream call."""

    async def test_get_tags_returns_json_payload(self):
        response = MagicMock()
        response.json.return_value = {
            "data": [
                {
                    "id": "tag-1",
                    "attributes": {"name": {"en": "Action"}, "group": "genre"},
                }
            ]
        }
        http_client = MagicMock()
        http_client.get = AsyncMock(return_value=response)

        client = MangaDexClient(http_client)
        result = await client.get_tags()

        http_client.get.assert_awaited_once_with("/manga/tag")
        response.raise_for_status.assert_called_once()
        self.assertEqual(result["data"][0]["id"], "tag-1")

    async def test_get_tags_raises_on_unsuccessful_response(self):
        response = MagicMock()
        response.raise_for_status.side_effect = Exception("upstream error")
        http_client = MagicMock()
        http_client.get = AsyncMock(return_value=response)

        client = MangaDexClient(http_client)
        with self.assertRaises(Exception):
            await client.get_tags()


class TestTagService(unittest.IsolatedAsyncioTestCase):
    """T2 — TagService cache, grouping, fallback, and expiry behaviour."""

    def setUp(self):
        self.cache = SimpleCache(ttl_seconds=60)
        self.client = MagicMock(spec=MangaDexClient)
        self.service = TagService(self.client, self.cache)

    async def test_get_tags_returns_cached_value_and_skips_upstream(self):
        cached = {
            "genres": [{"id": "cached", "name": "Cached"}],
            "themes": [],
            "formats": [],
            "content": [],
        }
        self.cache.set("mangadex:tags", cached)

        result = await self.service.get_tags()

        self.client.get_tags.assert_not_awaited()
        self.assertEqual(result, cached)

    async def test_get_tags_groups_upstream_data_and_caches_it(self):
        self.client.get_tags = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": "genre-1",
                        "attributes": {"name": {"en": "Action"}, "group": "genre"},
                    },
                    {
                        "id": "theme-1",
                        "attributes": {"name": {"en": "School"}, "group": "theme"},
                    },
                    {
                        "id": "format-1",
                        "attributes": {
                            "name": {"en": "Oneshot"},
                            "group": "format",
                        },
                    },
                    {
                        "id": "content-1",
                        "attributes": {
                            "name": {"en": "Gore"},
                            "group": "content",
                        },
                    },
                ]
            }
        )

        result = await self.service.get_tags()

        self.assertEqual(result["genres"], [{"id": "genre-1", "name": "Action"}])
        self.assertEqual(result["themes"], [{"id": "theme-1", "name": "School"}])
        self.assertEqual(result["formats"], [{"id": "format-1", "name": "Oneshot"}])
        self.assertEqual(result["content"], [{"id": "content-1", "name": "Gore"}])
        self.assertEqual(self.cache.get("mangadex:tags"), result)

    async def test_get_tags_ignores_unknown_groups(self):
        self.client.get_tags = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": "genre-1",
                        "attributes": {"name": {"en": "Action"}, "group": "genre"},
                    },
                    {
                        "id": "weird",
                        "attributes": {"name": {"en": "Weird"}, "group": "unknown"},
                    },
                ]
            }
        )

        result = await self.service.get_tags()

        self.assertEqual([tag["id"] for tag in result["genres"]], ["genre-1"])
        self.assertEqual(result["themes"], [])
        self.assertEqual(result["formats"], [])
        self.assertEqual(result["content"], [])

    async def test_get_tags_falls_back_and_caches_all_genres(self):
        self.client.get_tags = AsyncMock(side_effect=Exception("MangaDex down"))

        result = await self.service.get_tags()

        self.client.get_tags.assert_awaited_once()
        self.assertEqual(len(result["genres"]), len(GENRE_TAG_UUIDS))
        self.assertEqual(result["themes"], [])
        self.assertEqual(result["formats"], [])
        self.assertEqual(result["content"], [])
        for slug, uuid in GENRE_TAG_UUIDS.items():
            self.assertTrue(
                any(tag["id"] == uuid for tag in result["genres"]),
                f"Missing genre {slug}",
            )
        self.assertEqual(self.cache.get("mangadex:tags"), result)

    async def test_get_tags_refreshes_expired_cache(self):
        stale = {
            "genres": [{"id": "stale", "name": "Stale"}],
            "themes": [],
            "formats": [],
            "content": [],
        }
        fresh = {
            "genres": [{"id": "fresh", "name": "Fresh"}],
            "themes": [],
            "formats": [],
            "content": [],
        }
        self.cache._store["mangadex:tags"] = (0.0, stale)
        self.client.get_tags = AsyncMock(return_value={"data": []})

        with patch.object(TagService, "_group_tags", return_value=fresh):
            result = await self.service.get_tags()

        self.client.get_tags.assert_awaited_once()
        self.assertEqual(result, fresh)
        self.assertEqual(self.cache.get("mangadex:tags"), fresh)


class TestTagsRoute(unittest.TestCase):
    """T3 — GET /manga/tags depends on TagService via DI."""

    def setUp(self):
        self.app = create_hermetic_test_app()

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def test_route_uses_overridden_tag_service(self):
        fake_response = {
            "genres": [{"id": "override", "name": "Override"}],
            "themes": [],
            "formats": [],
            "content": [],
        }

        class FakeTagService:
            async def get_tags(self):
                return fake_response

        self.app.dependency_overrides[get_tag_service] = FakeTagService

        from fastapi.testclient import TestClient

        with TestClient(self.app) as client:
            response = client.get("/manga/tags")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), fake_response)
