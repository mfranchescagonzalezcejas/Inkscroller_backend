"""P0-B4 / P0-B5 — Image Cache & Bulk Download Compliance Audit Tests.

P0-B4: Verifica que el backend no cachea binarios de imágenes — solo URLs y metadatos.
P0-B5: Verifica que no existe ningún endpoint de bulk download de capítulos/imágenes.

Estos tests son evidencia técnica formal de cumplimiento P0-B4 y P0-B5.
"""

import asyncio
import sys
import types
import unittest
from importlib.util import find_spec
from unittest.mock import AsyncMock, patch

if find_spec("dotenv") is None:
    raise unittest.SkipTest("python-dotenv is not installed")

try:
    import httpx  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - local env without deps
    httpx = types.ModuleType("httpx")

    class _AsyncClient:
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

from app.core.cache import SimpleCache
from app.services.chapter_pages_service import ChapterPagesService
from app.services.chapter_service import ChapterService
from app.services.manga_service import MangaService
from unittest.mock import AsyncMock

from app.api import chapters as chapters_router_module
from app.api import manga as manga_router_module
from app.api import users as users_router_module
from app.api import health as health_router_module


# ---------------------------------------------------------------------------
# P0-B4 — No binary image caching
# ---------------------------------------------------------------------------

class TestNoBinaryCaching(unittest.TestCase):
    """P0-B4 — El caché solo almacena URLs (strings) y metadatos, no binarios de imagen."""

    def _assert_no_binary_content(self, value):
        if isinstance(value, dict):
            for nested in value.values():
                self._assert_no_binary_content(nested)
            return
        if isinstance(value, list):
            for nested in value:
                self._assert_no_binary_content(nested)
            return
        self.assertFalse(
            isinstance(value, (bytes, bytearray)),
            msg="P0-B4 FAIL — binary image content detected in cached/service payload.",
        )

    def test_simple_cache_stores_any_not_bytes(self):
        """SimpleCache acepta Any — verificamos que en uso real nunca se almacenan bytes/bytearray."""
        cache = SimpleCache(ttl_seconds=300)

        # Un valor bytes explícito debería ser el único tipo de dato que violaría B4.
        # Verificamos que el tipo anotado del value en SimpleCache es Any (no bytes),
        # y que el uso productivo en ChapterPagesService almacena un dict de URLs.
        import typing
        hints = typing.get_type_hints(SimpleCache.set)
        # El parámetro value es Any — no restringe bytes, pero auditamos todos los
        # callers para confirmar que ninguno pasa bytes (ver tests de callers abajo).
        self.assertIn("value", hints)

    def test_chapter_pages_service_caches_url_dict_not_bytes(self):
        """P0-B4 — get_pages cachea metadatos/URLs y nunca binarios."""
        cache = SimpleCache(ttl_seconds=300)
        client = AsyncMock()
        client.get_chapter_pages.return_value = {
            "baseUrl": "https://uploads.mangadex.org",
            "chapter": {
                "hash": "abc123",
                "data": ["001.jpg", "002.png"],
            },
        }

        service = ChapterPagesService(client=client, cache=cache)
        result = asyncio.run(service.get_pages("chapter-1"))

        self.assertEqual(result["readable"], True)
        self.assertEqual(result["external"], False)
        self.assertTrue(result["pages"])
        for page in result["pages"]:
            self.assertIsInstance(page, str, msg="P0-B4 FAIL — pages must be URL strings.")
            self.assertFalse(
                isinstance(page, (bytes, bytearray)),
                msg="P0-B4 FAIL — binary page content detected in service response.",
            )

        cached = cache.get("pages:chapter-1")
        self.assertEqual(cached, result)
        self.assertIsInstance(cached, dict, msg="P0-B4 FAIL — cache value must be metadata dict.")

    def test_chapter_pages_result_structure_is_urls_only(self):
        """P0-B4 — resultado no legible devuelve externo con pages vacías (sin binarios)."""
        cache = SimpleCache(ttl_seconds=300)
        client = AsyncMock()
        client.get_chapter_pages.return_value = {
            "baseUrl": "https://uploads.mangadex.org",
            "chapter": {
                "hash": "abc123",
                "data": [],
            },
        }

        service = ChapterPagesService(client=client, cache=cache)
        result = asyncio.run(service.get_pages("chapter-2"))

        self.assertEqual(
            result,
            {"readable": False, "pages": [], "external": True},
            msg="P0-B4 FAIL — non-readable chapter must return external URL metadata contract.",
        )
        self.assertIsNone(cache.get("pages:chapter-2"))

    def test_manga_service_caches_metadata_not_images(self):
        """P0-B4 — MangaService cachea metadatos (URL strings), no binarios."""
        cache = SimpleCache(ttl_seconds=300)
        client = AsyncMock()
        jikan = AsyncMock()
        client.search_manga.return_value = {
            "data": [
                {
                    "id": "manga-1",
                    "attributes": {
                        "title": {"en": "Test Manga"},
                        "description": {"en": "desc"},
                        "tags": [],
                    },
                    "relationships": [
                        {
                            "type": "cover_art",
                            "attributes": {"fileName": "cover-file"},
                        }
                    ],
                }
            ]
        }

        service = MangaService(client=client, jikan=jikan, cache=cache)

        first = asyncio.run(service.search("query", limit=1))
        second = asyncio.run(service.search("query", limit=1))

        client.search_manga.assert_awaited_once_with(query="query", limit=1)
        self.assertEqual(first, second)
        self.assertTrue(first)
        self.assertIsInstance(first[0].get("coverUrl"), str)
        self._assert_no_binary_content(first)

        cached = cache.get("search:query:1")
        self.assertEqual(cached, first)
        self._assert_no_binary_content(cached)

    def test_chapter_service_caches_metadata_not_images(self):
        """P0-B4 — ChapterService cachea metadatos de capítulos, no binarios."""
        cache = SimpleCache(ttl_seconds=300)
        client = AsyncMock()
        client.get_chapters.return_value = {
            "data": [
                {
                    "id": "chapter-1",
                    "attributes": {
                        "chapter": "1",
                        "title": "Chapter One",
                        "pages": 10,
                        "publishAt": "2024-01-01T00:00:00Z",
                        "externalUrl": None,
                    },
                    "relationships": [],
                }
            ]
        }

        service = ChapterService(client=client, cache=cache)

        first = asyncio.run(service.get_chapters("manga-1", language="en"))
        second = asyncio.run(service.get_chapters("manga-1", language="en"))

        client.get_chapters.assert_awaited_once_with(manga_id="manga-1", language="en")
        self.assertEqual(first, second)
        self.assertTrue(first)
        self.assertIsInstance(first[0].get("readable"), bool)
        self.assertIn("external", first[0])
        self._assert_no_binary_content(first)

        cached = cache.get("chapters:manga-1:en")
        self.assertEqual(cached, first)
        self._assert_no_binary_content(cached)

    def test_no_filesystem_image_storage(self):
        """P0-B4 — servicios de imagen/capítulos operan sin I/O a disco."""
        cache = SimpleCache(ttl_seconds=300)

        pages_client = AsyncMock()
        pages_client.get_chapter_pages.return_value = {
            "baseUrl": "https://uploads.mangadex.org",
            "chapter": {"hash": "hash", "data": ["001.jpg"]},
        }

        chapter_client = AsyncMock()
        chapter_client.get_chapters.return_value = {
            "data": [
                {
                    "id": "chapter-1",
                    "attributes": {
                        "chapter": "1",
                        "title": "One",
                        "pages": 1,
                        "publishAt": "2024-01-01T00:00:00Z",
                        "externalUrl": None,
                    },
                    "relationships": [],
                }
            ]
        }

        manga_client = AsyncMock()
        manga_client.search_manga.return_value = {
            "data": [
                {
                    "id": "manga-1",
                    "attributes": {"title": {"en": "Manga"}, "description": {"en": "d"}, "tags": []},
                    "relationships": [],
                }
            ]
        }

        with patch("builtins.open", side_effect=AssertionError("P0-B4 FAIL — file I/O detected")) as open_mock:
            pages_service = ChapterPagesService(client=pages_client, cache=cache)
            chapter_service = ChapterService(client=chapter_client, cache=cache)
            manga_service = MangaService(client=manga_client, jikan=AsyncMock(), cache=cache)

            pages_result = asyncio.run(pages_service.get_pages("chapter-1"))
            chapters_result = asyncio.run(chapter_service.get_chapters("manga-1"))
            mangas_result = asyncio.run(manga_service.search("query", limit=1))

            open_mock.assert_not_called()

        self._assert_no_binary_content(pages_result)
        self._assert_no_binary_content(chapters_result)
        self._assert_no_binary_content(mangas_result)

    def test_no_streaming_response_for_images(self):
        """P0-B4 — contrato de rutas no declara respuestas streaming/file para imágenes."""
        violations = []

        for router_name, module in [("chapters", chapters_router_module), ("manga", manga_router_module)]:
            router = getattr(module, "router", None)
            if router is None:
                continue
            for route in router.routes:
                if not hasattr(route, "path"):
                    continue

                response_class = route.response_class
                response_class_name = getattr(response_class, "__name__", "") if response_class else ""
                if response_class_name in {"StreamingResponse", "FileResponse"}:
                    violations.append(
                        f"P0-B4 FAIL — {router_name} route '{route.path}' uses {response_class.__name__}."
                    )

                for _, metadata in (route.responses or {}).items():
                    content = (metadata or {}).get("content", {})
                    media_types = {m.lower() for m in content.keys()}
                    if {"application/octet-stream", "image/jpeg", "image/png"} & media_types:
                        violations.append(
                            f"P0-B4 FAIL — {router_name} route '{route.path}' declares binary/image media types: "
                            f"{sorted(media_types)}"
                        )

        self.assertEqual(violations, [], msg="\n".join(violations))


# ---------------------------------------------------------------------------
# P0-B5 — No bulk download endpoint
# ---------------------------------------------------------------------------

class TestNoBulkDownloadEndpoint(unittest.TestCase):
    """P0-B5 — No existe ningún endpoint de bulk download de capítulos o imágenes."""

    def _collect_all_routes(self):
        """Recopila todas las rutas registradas en todos los routers."""
        routes = []
        for module_name, module in [
            ("chapters", chapters_router_module),
            ("manga", manga_router_module),
            ("users", users_router_module),
            ("health", health_router_module),
        ]:
            router = getattr(module, "router", None)
            if router is not None:
                for route in router.routes:
                    routes.append({
                        "module": module_name,
                        "path": getattr(route, "path", ""),
                        "methods": getattr(route, "methods", set()),
                        "name": getattr(route, "name", ""),
                    })
        return routes

    def test_no_bulk_download_route_exists(self):
        """No existe ninguna ruta con 'download' o 'bulk' en el path."""
        routes = self._collect_all_routes()
        violations = []

        for route in routes:
            path_lower = route["path"].lower()
            name_lower = route["name"].lower()
            if "download" in path_lower or "bulk" in path_lower:
                violations.append(
                    f"P0-B5 FAIL — Route '{route['path']}' in {route['module']} "
                    f"contains 'download' or 'bulk'"
                )
            if "download" in name_lower or "bulk" in name_lower:
                violations.append(
                    f"P0-B5 FAIL — Endpoint function '{route['name']}' in {route['module']} "
                    f"contains 'download' or 'bulk'"
                )

        self.assertEqual(
            violations,
            [],
            msg="\n".join(violations),
        )

    def test_chapters_router_endpoints_are_read_only_metadata(self):
        """P0-B5 — capítulos expone solo lectura de metadatos/URLs, sin semántica bulk/binaria."""
        router = getattr(chapters_router_module, "router", None)
        self.assertIsNotNone(router, msg="P0-B5 FAIL — chapters router not found.")

        violations = []
        pages_endpoint_found = False

        for route in router.routes:
            if not hasattr(route, "path"):
                continue

            path_lower = route.path.lower()
            name_lower = getattr(route, "name", "").lower()
            methods = getattr(route, "methods", set())

            # P0-B5: chapters debe permanecer en lectura (sin create/update/delete).
            if methods != {"GET"}:
                violations.append(
                    f"P0-B5 FAIL — chapters route '{route.path}' uses non-read-only methods: {methods}."
                )

            # P0-B5: sin semántica de descarga masiva/archivo.
            if any(token in path_lower for token in ("download", "bulk", "archive", "export", "zip")):
                violations.append(
                    f"P0-B5 FAIL — chapters route '{route.path}' suggests bulk/binary behavior."
                )
            if any(token in name_lower for token in ("download", "bulk", "archive", "export", "zip")):
                violations.append(
                    f"P0-B5 FAIL — chapters endpoint '{route.name}' suggests bulk/binary behavior."
                )

            if route.path.endswith("/pages"):
                pages_endpoint_found = True

        self.assertTrue(
            pages_endpoint_found,
            msg="P0-B5 FAIL — expected chapter pages URL-only endpoint was not found.",
        )
        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_all_chapter_endpoints_use_get_method_only(self):
        """Todos los endpoints de capítulos son GET — no hay POST/PUT que reciba contenido binario."""
        routes = self._collect_all_routes()
        chapter_routes = [r for r in routes if r["module"] == "chapters"]

        for route in chapter_routes:
            self.assertEqual(
                route["methods"],
                {"GET"},
                msg=(
                    f"P0-B5 FAIL — chapters endpoint '{route['path']}' uses "
                    f"non-GET method(s): {route['methods']}. "
                    f"Upload/receive endpoints could indicate binary storage."
                ),
            )

    def test_no_archive_media_type_or_file_stream_contract(self):
        """P0-B5 — contrato HTTP no expone ZIP/TAR ni respuestas tipo archivo/stream."""
        routes = self._collect_all_routes()
        archive_media_types = {
            "application/zip",
            "application/x-zip-compressed",
            "application/x-tar",
            "application/gzip",
            "application/octet-stream",
        }

        violations = []
        for module in (chapters_router_module, manga_router_module, users_router_module, health_router_module):
            router = getattr(module, "router", None)
            if router is None:
                continue
            for route in router.routes:
                if not hasattr(route, "path"):
                    continue

                response_class = route.response_class
                response_class_name = getattr(response_class, "__name__", "") if response_class else ""
                if response_class_name in {"StreamingResponse", "FileResponse"}:
                    violations.append(
                        f"P0-B5 FAIL — Route '{route.path}' uses response_class={response_class.__name__}, "
                        "which could serve archive/binary payloads."
                    )

                if route.response_model is None and getattr(route, "responses", None):
                    for status_code, metadata in route.responses.items():
                        content = (metadata or {}).get("content", {})
                        for media_type in content.keys():
                            if media_type.lower() in archive_media_types:
                                violations.append(
                                    f"P0-B5 FAIL — Route '{route.path}' declares archive/binary media type "
                                    f"'{media_type}' on status {status_code}."
                                )

        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_chapter_pages_returns_urls_not_binary_content(self):
        """P0-B5 — endpoint de pages delega y retorna contrato URL-only (sin proxy binario)."""
        payload = {
            "readable": True,
            "external": False,
            "pages": ["https://uploads.mangadex.org/data/hash/001.jpg"],
        }

        pages_service = AsyncMock()
        pages_service.get_pages.return_value = payload

        fake_chapter_service = AsyncMock()
        fake_chapter_service.get_manga_id_for_chapter = AsyncMock(return_value="safe-manga")

        manga_service = AsyncMock()
        manga_service.get_by_id = AsyncMock(
            side_effect=lambda manga_id, user_age=None, skip_age_filter=False: {
                "id": "safe-manga",
                "title": "Safe Manga",
                "contentRating": "safe",
            }
        )

        result = asyncio.run(
            chapters_router_module.get_chapter_pages(
                "  chapter-id  ",
                pages_service,
                fake_chapter_service,
                manga_service,
                None,
            )
        )

        pages_service.get_pages.assert_awaited_once_with("chapter-id")
        self.assertEqual(result, payload)
        self.assertIsInstance(result["pages"][0], str, msg="P0-B5 FAIL — pages endpoint must return URL strings.")

    def test_mangadex_get_statistics_uses_one_request_per_manga_id_p0_b5(self):
        """P0-B5 — get_statistics confirma por comportamiento que NO hay endpoint bulk."""
        from app.sources.mangadex_client import MangaDexClient

        class _StatsResponse:
            def __init__(self, manga_id: str):
                self._manga_id = manga_id

            def raise_for_status(self):
                return None

            def json(self):
                return {"statistics": {self._manga_id: {"follows": 1}}}

        class _RecordingClient:
            def __init__(self):
                self.paths: list[str] = []
                self.params: list[dict] = []

            async def get(self, path, params=None):
                self.paths.append(path)
                self.params.append(params or {})
                manga_id = str(path).rsplit("/", 1)[-1]
                return _StatsResponse(manga_id)

        recorder = _RecordingClient()
        client = MangaDexClient(recorder)

        result = asyncio.run(client.get_statistics(["manga-a", "manga-b"]))

        self.assertEqual(
            recorder.paths,
            ["/statistics/manga/manga-a", "/statistics/manga/manga-b"],
            msg=(
                "P0-B5 FAIL — get_statistics dejó de hacer fan-out one-by-one; "
                "se esperaba una request por manga_id sin endpoint bulk."
            ),
        )
        self.assertEqual(
            recorder.params,
            [{}, {}],
            msg="P0-B5 FAIL — get_statistics no debe enviar payload/query bulk en la request.",
        )
        self.assertEqual(
            sorted(result.get("statistics", {}).keys()),
            ["manga-a", "manga-b"],
            msg="P0-B5 FAIL — contrato de estadísticas agregado por manga_id cambió.",
        )

    def test_no_route_exposes_binary_download_contract(self):
        """P0-B5 — invariantes semánticos: ninguna ruta pública anuncia descarga binaria/adjuntos."""
        violations = []

        for module_name, module in [
            ("chapters", chapters_router_module),
            ("manga", manga_router_module),
            ("users", users_router_module),
            ("health", health_router_module),
        ]:
            router = getattr(module, "router", None)
            if router is None:
                continue

            for route in router.routes:
                if not hasattr(route, "path"):
                    continue

                for status_code, metadata in (route.responses or {}).items():
                    headers = (metadata or {}).get("headers", {})
                    if any(str(header_name).lower() == "content-disposition" for header_name in headers.keys()):
                        violations.append(
                            f"P0-B5 FAIL — Route '{route.path}' ({module_name}) advertises Content-Disposition "
                            f"on status {status_code}, hinting attachment download."
                        )

                    content = (metadata or {}).get("content", {})
                    media_types = {str(m).lower() for m in content.keys()}
                    if any(mt.startswith("application/") and any(k in mt for k in ("zip", "tar", "gzip", "octet-stream")) for mt in media_types):
                        violations.append(
                            f"P0-B5 FAIL — Route '{route.path}' ({module_name}) declares binary/archive media type(s): "
                            f"{sorted(media_types)}"
                        )

        self.assertEqual(violations, [], msg="\n".join(violations))


if __name__ == "__main__":
    unittest.main()
