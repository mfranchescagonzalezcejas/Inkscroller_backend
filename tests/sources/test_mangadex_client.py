"""Tests for the MangaDex client query contract."""

import asyncio
import unittest
from time import monotonic
from unittest.mock import AsyncMock, patch

import httpx

from app.sources.mangadex_client import MangaDexClient, _MangaDexRateLimiter


class _FakeResponse:
    headers: dict[str, str] = {}
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"data": []}


class _RecordingAsyncClient:
    def __init__(self):
        self.requests: list[tuple[str, dict]] = []

    async def get(self, path, params=None):
        self.requests.append((path, params or {}))
        return _FakeResponse()


class _ThrottledAsyncClient(_RecordingAsyncClient):
    async def get(self, path, params=None):
        await super().get(path, params)
        return _FakeResponse()


class _RateLimitedResponse:
    def __init__(self, retry_after: str | None = None) -> None:
        self.headers = {} if retry_after is None else {"Retry-After": retry_after}
        self.status_code = 429

    def raise_for_status(self):
        response = httpx.Response(
            429,
            headers=self.headers,
            request=httpx.Request("GET", "https://api.mangadex.org/manga"),
        )
        raise httpx.HTTPStatusError(
            "Too Many Requests", request=response.request, response=response
        )


class _FakeLoop:
    def __init__(self) -> None:
        self.now = 0.0

    def time(self) -> float:
        return self.now


class TestMangaDexClientGetChapters(unittest.IsolatedAsyncioTestCase):
    async def test_get_chapters_omits_language_filter_when_none(self):
        recorder = _RecordingAsyncClient()
        client = MangaDexClient(recorder)

        await client.get_chapters("manga-1", language=None)

        self.assertEqual(len(recorder.requests), 1)
        path, params = recorder.requests[0]
        self.assertEqual(path, "/chapter")
        self.assertNotIn("translatedLanguage[]", params)
        self.assertEqual(params.get("manga"), "manga-1")

    async def test_get_chapters_accepts_list_of_languages(self):
        recorder = _RecordingAsyncClient()
        client = MangaDexClient(recorder)

        await client.get_chapters("manga-1", language=["en", "es"])

        self.assertEqual(len(recorder.requests), 1)
        path, params = recorder.requests[0]
        self.assertEqual(path, "/chapter")
        self.assertEqual(params.get("translatedLanguage[]"), ["en", "es"])

    async def test_get_chapters_keeps_single_language_filter(self):
        recorder = _RecordingAsyncClient()
        client = MangaDexClient(recorder)

        await client.get_chapters("manga-1", language="es")

        self.assertEqual(len(recorder.requests), 1)
        path, params = recorder.requests[0]
        self.assertEqual(path, "/chapter")
        self.assertEqual(params.get("translatedLanguage[]"), "es")


class TestMangaDexClientThrottling(unittest.IsolatedAsyncioTestCase):
    async def test_clients_share_rate_limit(self):
        limiter = _MangaDexRateLimiter(interval_seconds=0.01)
        primary_requests = _ThrottledAsyncClient()
        worker_requests = _ThrottledAsyncClient()
        primary = MangaDexClient(primary_requests, limiter)
        worker = MangaDexClient(worker_requests, limiter)

        started_at = monotonic()
        await asyncio.gather(primary.get_tags(), worker.get_tags())

        self.assertEqual(len(primary_requests.requests), 1)
        self.assertEqual(len(worker_requests.requests), 1)
        self.assertGreaterEqual(monotonic() - started_at, 0.009)

    async def test_429_is_not_retried(self):
        requester = _RecordingAsyncClient()
        requester.get = AsyncMock(return_value=_RateLimitedResponse("1"))
        limiter = _MangaDexRateLimiter(0)
        client = MangaDexClient(requester, limiter)

        with patch("app.core.resilience.asyncio.sleep", new=AsyncMock()):
            with self.assertRaises(httpx.HTTPStatusError):
                await client.get_tags()

        requester.get.assert_awaited_once()
        self.assertGreater(limiter._next_request_at, asyncio.get_running_loop().time())

    async def test_pre_reserved_request_waits_for_new_cooldown(self):
        clock = _FakeLoop()
        limiter = _MangaDexRateLimiter(interval_seconds=0.25)
        limiter._next_request_at = 0.25
        requester = _RecordingAsyncClient()
        client = MangaDexClient(requester, limiter)

        async def advance_clock(delay: float) -> None:
            if clock.now == 0:
                await limiter.cooldown(1)
            clock.now += delay

        with (
            patch(
                "app.sources.mangadex_client.asyncio.get_running_loop",
                return_value=clock,
            ),
            patch("app.sources.mangadex_client.asyncio.sleep", new=advance_clock),
        ):
            await client._get("/manga")

        self.assertEqual(clock.time(), 1)
        self.assertEqual(len(requester.requests), 1)


if __name__ == "__main__":
    unittest.main()
