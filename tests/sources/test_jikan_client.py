"""Tests for JikanClient — search and get_manga_by_id."""

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock

import httpx

from app.sources.jikan_client import JikanClient


class TestJikanClientGetMangaById(IsolatedAsyncioTestCase):
    """JikanClient.get_manga_by_id — contract tests."""

    def setUp(self):
        self.client = MagicMock()
        self.client.get = AsyncMock()
        self.jikan = JikanClient(self.client)

    async def test_get_manga_by_id_returns_parsed_data(self):
        """get_manga_by_id returns full JSON on success."""
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json = MagicMock(
            return_value={"data": {"mal_id": 12345, "title": "Naruto"}}
        )
        self.client.get.return_value = response

        result = await self.jikan.get_manga_by_id(12345)

        self.client.get.assert_awaited_once_with("/manga/12345")
        self.assertEqual(result, {"data": {"mal_id": 12345, "title": "Naruto"}})

    async def test_get_manga_by_id_raises_on_http_error(self):
        """get_manga_by_id raises HTTPStatusError on non-2xx."""
        error_response = MagicMock()
        error_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "404 error",
                request=httpx.Request("GET", "http://test"),
                response=httpx.Response(404),
            )
        )
        self.client.get.return_value = error_response

        with self.assertRaises(httpx.HTTPStatusError):
            await self.jikan.get_manga_by_id(99999)
