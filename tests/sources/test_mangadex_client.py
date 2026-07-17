"""Tests for the MangaDex client query contract."""

import unittest

from app.sources.mangadex_client import MangaDexClient


class _FakeResponse:
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


if __name__ == "__main__":
    unittest.main()
