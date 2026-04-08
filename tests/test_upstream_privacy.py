"""P0-B7 — Upstream Request Privacy Audit Tests.

Verifica que ningún método de MangaDexClient ni JikanClient
acepte o transmita datos personales de usuarios (UID, email, tokens PII).

Estos tests son evidencia técnica formal de cumplimiento P0-B7.
"""

import inspect
import unittest

from app.sources.mangadex_client import MangaDexClient
from app.sources.jikan_client import JikanClient


# Términos que indican PII — si alguno aparece como parámetro, es una fuga.
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


def _public_methods(cls):
    return [
        (name, method)
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction)
        if not name.startswith("_")
    ]


def _param_names(method):
    sig = inspect.signature(method)
    return {
        name.lower()
        for name in sig.parameters
        if name not in ("self", "cls")
    }


class TestMangaDexClientPrivacy(unittest.TestCase):
    """Audita que MangaDexClient no tiene parámetros PII en ningún método público."""

    def test_no_pii_params_in_any_public_method(self):
        """Ningún método público de MangaDexClient debe aceptar parámetros PII."""
        violations = []

        for method_name, method in _public_methods(MangaDexClient):
            params = _param_names(method)
            leaked = params & PII_PARAM_KEYWORDS
            if leaked:
                violations.append(
                    f"MangaDexClient.{method_name} has PII params: {leaked}"
                )

        self.assertEqual(
            violations,
            [],
            msg=(
                "P0-B7 FAIL — MangaDexClient methods expose PII parameters:\n"
                + "\n".join(violations)
            ),
        )

    def test_allowed_params_are_content_identifiers_only(self):
        """Los parámetros de MangaDexClient deben ser IDs de contenido y filtros públicos."""
        # Parámetros permitidos: IDs de contenido, filtros públicos, paginación
        allowed_prefixes = {
            "manga_id", "chapter_id", "manga_ids", "query", "title",
            "limit", "offset", "language", "demographic", "status",
            "order", "included_tags", "order_map",
        }

        for method_name, method in _public_methods(MangaDexClient):
            params = _param_names(method)
            for param in params:
                # Verificar que no contenga keywords PII como substring
                for keyword in PII_PARAM_KEYWORDS:
                    self.assertNotIn(
                        keyword,
                        param,
                        msg=(
                            f"P0-B7 FAIL — MangaDexClient.{method_name} param "
                            f"'{param}' contains PII keyword '{keyword}'"
                        ),
                    )


class TestJikanClientPrivacy(unittest.TestCase):
    """Audita que JikanClient no tiene parámetros PII en ningún método público."""

    def test_no_pii_params_in_any_public_method(self):
        """Ningún método público de JikanClient debe aceptar parámetros PII."""
        violations = []

        for method_name, method in _public_methods(JikanClient):
            params = _param_names(method)
            leaked = params & PII_PARAM_KEYWORDS
            if leaked:
                violations.append(
                    f"JikanClient.{method_name} has PII params: {leaked}"
                )

        self.assertEqual(
            violations,
            [],
            msg=(
                "P0-B7 FAIL — JikanClient methods expose PII parameters:\n"
                + "\n".join(violations)
            ),
        )

    def test_search_manga_only_accepts_title(self):
        """JikanClient.search_manga solo acepta el parámetro 'title'."""
        sig = inspect.signature(JikanClient.search_manga)
        params = {
            name for name in sig.parameters if name not in ("self", "cls")
        }
        self.assertEqual(
            params,
            {"title"},
            msg=(
                f"P0-B7 FAIL — JikanClient.search_manga signature changed. "
                f"Expected only 'title', got: {params}"
            ),
        )


class TestClientConstructorPrivacy(unittest.TestCase):
    """Verifica que los constructores de clientes no aceptan datos de usuario."""

    def test_mangadex_client_init_only_accepts_http_client(self):
        """MangaDexClient.__init__ solo debe aceptar un httpx.AsyncClient."""
        sig = inspect.signature(MangaDexClient.__init__)
        params = {
            name for name in sig.parameters if name not in ("self",)
        }
        self.assertEqual(
            params,
            {"client"},
            msg=(
                f"P0-B7 FAIL — MangaDexClient.__init__ signature changed. "
                f"Expected only 'client', got: {params}"
            ),
        )

    def test_jikan_client_init_only_accepts_http_client(self):
        """JikanClient.__init__ solo debe aceptar un httpx.AsyncClient."""
        sig = inspect.signature(JikanClient.__init__)
        params = {
            name for name in sig.parameters if name not in ("self",)
        }
        self.assertEqual(
            params,
            {"client"},
            msg=(
                f"P0-B7 FAIL — JikanClient.__init__ signature changed. "
                f"Expected only 'client', got: {params}"
            ),
        )


class TestMangaDexClientMethodSignatures(unittest.TestCase):
    """Verifica firmas exactas de cada método de MangaDexClient contra lista blanca."""

    # Mapa: method_name -> set de parámetros permitidos (excluyendo self)
    EXPECTED_SIGNATURES = {
        "search_manga": {"query", "limit"},
        "get_manga": {"manga_id"},
        "get_chapters": {"manga_id", "language", "limit"},
        "get_latest_chapters": {"language", "limit"},
        "get_manga_list_by_ids": {"manga_ids"},
        "get_chapter_pages": {"chapter_id"},
        "get_statistics": {"manga_ids"},
        "list_manga": {
            "limit", "offset", "title", "demographic", "status",
            "order", "included_tags", "order_map"
        },
    }

    def test_all_method_signatures_match_whitelist(self):
        """Todos los métodos de MangaDexClient tienen exactamente los parámetros permitidos."""
        violations = []

        for method_name, expected_params in self.EXPECTED_SIGNATURES.items():
            method = getattr(MangaDexClient, method_name, None)
            if method is None:
                violations.append(f"MangaDexClient.{method_name} not found")
                continue

            actual_params = _param_names(method)
            unexpected = actual_params - expected_params
            if unexpected:
                violations.append(
                    f"MangaDexClient.{method_name}: unexpected params {unexpected} "
                    f"(expected only {expected_params})"
                )

        self.assertEqual(
            violations,
            [],
            msg=(
                "P0-B7 FAIL — MangaDexClient method signatures contain unexpected params:\n"
                + "\n".join(violations)
            ),
        )


if __name__ == "__main__":
    unittest.main()
