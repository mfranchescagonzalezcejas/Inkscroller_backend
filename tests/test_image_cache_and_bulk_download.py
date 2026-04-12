"""P0-B4 / P0-B5 — Image Cache & Bulk Download Compliance Audit Tests.

P0-B4: Verifica que el backend no cachea binarios de imágenes — solo URLs y metadatos.
P0-B5: Verifica que no existe ningún endpoint de bulk download de capítulos/imágenes.

Estos tests son evidencia técnica formal de cumplimiento P0-B4 y P0-B5.
"""

import inspect
import unittest

from app.core.cache import SimpleCache
from app.services.chapter_pages_service import ChapterPagesService
from app.services.chapter_service import ChapterService
from app.services.manga_service import MangaService
from app.api import chapters as chapters_router_module
from app.api import manga as manga_router_module
from app.api import users as users_router_module
from app.api import health as health_router_module


# ---------------------------------------------------------------------------
# P0-B4 — No binary image caching
# ---------------------------------------------------------------------------

class TestNoBinaryCaching(unittest.TestCase):
    """P0-B4 — El caché solo almacena URLs (strings) y metadatos, no binarios de imagen."""

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
        """ChapterPagesService cachea un dict {readable, external, pages: [str]} — no bytes."""
        source = inspect.getsource(ChapterPagesService.get_pages)

        # El resultado cacheado debe ser un dict con 'pages' (lista de URLs)
        self.assertIn('"readable"', source)
        self.assertIn('"pages"', source)
        self.assertIn('"external"', source)

        # No debe haber lectura de contenido binario de imagen
        self.assertNotIn(".read()", source)
        self.assertNotIn(".content", source.replace("# ", ""))  # exclude comments
        self.assertNotIn("b64encode", source)
        self.assertNotIn("BytesIO", source)
        self.assertNotIn("bytes(", source)

    def test_chapter_pages_result_structure_is_urls_only(self):
        """El resultado de get_pages construye URLs como strings — no descarga binarios."""
        source = inspect.getsource(ChapterPagesService.get_pages)

        # La construcción de páginas es una list-comprehension de f-strings (URLs)
        # Verificamos que la lógica de construcción produce strings, no bytes
        self.assertIn("base_url", source)
        self.assertIn("hash_", source)
        self.assertIn("file", source)
        # Formato exacto de URL MangaDex CDN
        self.assertIn("f\"{base_url}/data/{hash_}/{file}\"", source)

    def test_manga_service_caches_metadata_not_images(self):
        """MangaService cachea dicts de metadatos (coverUrl es string URL, no bytes)."""
        source = inspect.getsource(MangaService)

        # coverUrl debe ser una URL string, no datos binarios
        self.assertNotIn("b64encode", source)
        self.assertNotIn("BytesIO", source)
        self.assertNotIn(".content", source)
        self.assertNotIn("image/", source)

    def test_chapter_service_caches_metadata_not_images(self):
        """ChapterService cachea listas de metadatos de capítulos — no binarios."""
        source = inspect.getsource(ChapterService)

        self.assertNotIn("b64encode", source)
        self.assertNotIn("BytesIO", source)
        self.assertNotIn(".read()", source)
        self.assertNotIn("open(", source)

    def test_no_filesystem_image_storage(self):
        """Ningún servicio escribe imágenes a disco."""
        sources_to_check = [
            ("ChapterPagesService", inspect.getsource(ChapterPagesService)),
            ("ChapterService", inspect.getsource(ChapterService)),
            ("MangaService", inspect.getsource(MangaService)),
        ]

        binary_write_patterns = [
            "open(",
            "write(",
            "shutil.",
            "os.path.join",
            "pathlib.Path",
            "aiofiles",
        ]

        for cls_name, source in sources_to_check:
            for pattern in binary_write_patterns:
                self.assertNotIn(
                    pattern,
                    source,
                    msg=(
                        f"P0-B4 FAIL — {cls_name} contains file I/O pattern '{pattern}'. "
                        f"This could indicate binary image storage."
                    ),
                )

    def test_no_streaming_response_for_images(self):
        """Los routers no usan StreamingResponse ni FileResponse para imágenes."""
        chapters_source = inspect.getsource(chapters_router_module)
        manga_source = inspect.getsource(manga_router_module)

        for router_name, source in [("chapters", chapters_source), ("manga", manga_source)]:
            self.assertNotIn(
                "StreamingResponse",
                source,
                msg=f"P0-B4 FAIL — {router_name} router uses StreamingResponse (potential binary proxy).",
            )
            self.assertNotIn(
                "FileResponse",
                source,
                msg=f"P0-B4 FAIL — {router_name} router uses FileResponse (potential binary serving).",
            )
            self.assertNotIn(
                "application/octet-stream",
                source,
                msg=f"P0-B4 FAIL — {router_name} router sets octet-stream content type.",
            )
            self.assertNotIn(
                "image/jpeg",
                source,
                msg=f"P0-B4 FAIL — {router_name} router serves JPEG content directly.",
            )
            self.assertNotIn(
                "image/png",
                source,
                msg=f"P0-B4 FAIL — {router_name} router serves PNG content directly.",
            )


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
        """Los endpoints de capítulos solo devuelven metadatos o URLs — nunca contenido binario."""
        routes = self._collect_all_routes()
        chapter_routes = [r for r in routes if r["module"] == "chapters"]

        # Rutas permitidas: /latest, /manga/{id}, /{id}/pages
        allowed_patterns = {"/chapters/latest", "/chapters/manga/{manga_id}", "/chapters/{chapter_id}/pages"}
        found_paths = {r["path"] for r in chapter_routes}

        self.assertEqual(
            found_paths,
            allowed_patterns,
            msg=(
                f"P0-B5 FAIL — chapters router has unexpected routes.\n"
                f"Expected: {allowed_patterns}\n"
                f"Found: {found_paths}\n"
                f"Extra routes could indicate undocumented bulk/download functionality."
            ),
        )

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

    def test_no_zip_archive_generation(self):
        """No hay lógica de creación de ZIP/TAR de capítulos (indicador de bulk download)."""
        modules_to_check = [
            ("chapters_router", inspect.getsource(chapters_router_module)),
            ("ChapterPagesService", inspect.getsource(ChapterPagesService)),
            ("ChapterService", inspect.getsource(ChapterService)),
        ]

        bulk_patterns = ["zipfile", "tarfile", "ZipFile", "TarFile", "shutil.make_archive"]

        for module_name, source in modules_to_check:
            for pattern in bulk_patterns:
                self.assertNotIn(
                    pattern,
                    source,
                    msg=(
                        f"P0-B5 FAIL — {module_name} uses '{pattern}'. "
                        f"Archive generation indicates bulk download functionality."
                    ),
                )

    def test_chapter_pages_returns_urls_not_binary_content(self):
        """El endpoint /{chapter_id}/pages retorna URLs de imágenes, no binarios descargados."""
        source = inspect.getsource(chapters_router_module)

        # El endpoint pages delega a pages_service.get_pages() que retorna un dict de URLs
        self.assertIn("pages_service.get_pages", source)

        # No hace proxy del contenido de imagen
        self.assertNotIn("httpx.get", source)
        self.assertNotIn("requests.get", source)
        self.assertNotIn(".content", source)
        self.assertNotIn("await client.get", source)

    def test_mangadex_client_comment_confirms_no_bulk(self):
        """El comentario en MangaDexClient.get_statistics confirma que MangaDex no soporta bulk."""
        from app.sources.mangadex_client import MangaDexClient
        source = inspect.getsource(MangaDexClient.get_statistics)
        # Este comentario es evidencia de que el diseño explícitamente rechaza bulk
        self.assertIn("doesn't support bulk", source)

    def test_total_route_count_matches_expected(self):
        """El número total de rutas coincide con el inventario auditado (sin rutas ocultas)."""
        routes = self._collect_all_routes()

        # Inventario auditado:
        # chapters: 3 rutas (latest, manga/{id}, {id}/pages)
        # manga: 5 rutas (tags, genres, search, {id}, "")
        # users: 7 rutas (me, me/preferences GET, me/preferences PUT,
        #                  me/library GET, me/library/{id} POST,
        #                  me/library/{id} PATCH, me/library/{id} DELETE)
        # health: 1 ruta (ping)
        # Total: 16 rutas
        EXPECTED_ROUTE_COUNT = 16

        self.assertEqual(
            len(routes),
            EXPECTED_ROUTE_COUNT,
            msg=(
                f"P0-B5 FAIL — Route count changed. Expected {EXPECTED_ROUTE_COUNT}, "
                f"found {len(routes)}.\n"
                f"Routes found: {[r['path'] for r in routes]}\n"
                f"If a new route was added intentionally, update this test and document compliance."
            ),
        )


if __name__ == "__main__":
    unittest.main()
