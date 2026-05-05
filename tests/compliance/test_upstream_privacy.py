"""P0-B7 — Upstream Request Privacy Audit Tests.

Valida privacidad por comportamiento en el borde HTTP saliente:
los clientes solo deben enviar filtros públicos de contenido, nunca PII.
"""

import sys
import types
import unittest

try:
    import httpx  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - CI/dev sin deps completas
    httpx = types.ModuleType("httpx")

    class _AsyncClient:  # noqa: D401 - stub mínimo para imports
        pass

    class _ConnectError(Exception):
        pass

    class _HTTPStatusError(Exception):
        pass

    class _TimeoutException(Exception):
        pass

    httpx.AsyncClient = _AsyncClient
    httpx.ConnectError = _ConnectError
    httpx.HTTPStatusError = _HTTPStatusError
    httpx.TimeoutException = _TimeoutException
    sys.modules["httpx"] = httpx

from app.sources.jikan_client import JikanClient
from app.sources.mangadex_client import MangaDexClient


PII_PARAM_KEYWORDS = {
    "uid",
    "user_id",
    "email",
    "token",
    "firebase",
    "credential",
    "auth",
    "password",
    "secret",
    "api_key",
    "apikey",
}


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


def _flatten_param_names(params: dict) -> set[str]:
    return {str(key).lower() for key in params.keys()}


class TestUpstreamPrivacyBehavior(unittest.IsolatedAsyncioTestCase):
    """P0-B7: anti-fragile checks centrados en payload HTTP saliente."""

    def assert_no_pii_in_outbound_params(self, client_name: str, path: str, params: dict):
        outbound_keys = _flatten_param_names(params)
        violations = {
            f"{key} contains {keyword}"
            for key in outbound_keys
            for keyword in PII_PARAM_KEYWORDS
            if keyword in key
        }
        self.assertEqual(
            violations,
            set(),
            msg=(
                f"P0-B7 FAIL — {client_name} leaked PII-like outbound query keys "
                f"on {path}: {sorted(violations)}"
            ),
        )

    async def test_mangadex_public_methods_only_emit_public_filters(self):
        recorder = _RecordingAsyncClient()
        client = MangaDexClient(recorder)

        await client.search_manga("berserk", limit=3)
        await client.get_manga("manga-123")
        await client.get_chapters("manga-123", language="es", limit=7)
        await client.get_latest_chapters(language="en", limit=2)
        await client.get_manga_list_by_ids(["a", "b"])
        await client.get_chapter_pages("chapter-88")
        await client.list_manga(limit=5, offset=0, title="vinland")
        await client.get_statistics(["a", "b"])

        self.assertGreater(
            len(recorder.requests),
            0,
            msg="P0-B7 FAIL — expected outbound MangaDex requests but recorded none",
        )

        for path, params in recorder.requests:
            self.assert_no_pii_in_outbound_params("MangaDexClient", path, params)

    async def test_jikan_search_only_emits_public_query_contract(self):
        recorder = _RecordingAsyncClient()
        client = JikanClient(recorder)

        await client.search_manga("monster")

        self.assertEqual(
            len(recorder.requests),
            1,
            msg="P0-B7 FAIL — JikanClient should emit exactly one outbound request",
        )

        path, params = recorder.requests[0]
        self.assertEqual(path, "/manga", msg="P0-B7 FAIL — unexpected Jikan path")
        self.assertEqual(
            set(params.keys()),
            {"q", "limit"},
            msg=(
                "P0-B7 FAIL — JikanClient outbound query contract changed; "
                "expected only public keys {'q', 'limit'}"
            ),
        )
        self.assert_no_pii_in_outbound_params("JikanClient", path, params)


if __name__ == "__main__":
    unittest.main()
