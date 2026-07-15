import asyncio
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from app.core.config import Settings
from app.core.security_headers import get_security_headers
from tests.api.helpers import create_hermetic_test_app


class RequestSecuritySettingsTests(unittest.TestCase):
    def test_settings_defaults_request_timeout_and_body_limit(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
            settings = Settings()

        self.assertEqual(settings.request_timeout_seconds, 30)
        self.assertEqual(settings.max_request_body_mb, 5)

    def test_settings_env_override_for_request_timeout_and_body_limit(self):
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "development",
                "REQUEST_TIMEOUT_SECONDS": "60",
                "MAX_REQUEST_BODY_MB": "10",
            },
            clear=True,
        ):
            settings = Settings()

        self.assertEqual(settings.request_timeout_seconds, 60)
        self.assertEqual(settings.max_request_body_mb, 10)


class SecurityHeadersTests(unittest.TestCase):
    def test_production_headers_include_hsts(self):
        headers = get_security_headers(is_production=True)

        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["X-XSS-Protection"], "0")
        self.assertEqual(headers["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertIn("Strict-Transport-Security", headers)
        self.assertEqual(
            headers["Strict-Transport-Security"],
            "max-age=31536000; includeSubDomains",
        )
        self.assertIn("Content-Security-Policy-Report-Only", headers)

    def test_non_production_headers_omit_hsts(self):
        headers = get_security_headers(is_production=False)

        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["X-XSS-Protection"], "0")
        self.assertEqual(headers["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertNotIn("Strict-Transport-Security", headers)
        self.assertIn("Content-Security-Policy-Report-Only", headers)

    def test_x_xss_protection_value_is_zero(self):
        headers = get_security_headers(is_production=True)
        self.assertEqual(headers["X-XSS-Protection"], "0")


class RequestBodyLimitMiddlewareTests(unittest.TestCase):
    """3.1 RED — request body size enforcement."""

    def _csp_body_of_size(self, size: int) -> bytes:
        prefix = b'{"csp-report":{"padding":"'
        suffix = b'"}}'
        padding = size - len(prefix) - len(suffix)
        if padding < 0:
            raise ValueError("size too small for fixture")
        return prefix + b"x" * padding + suffix

    def setUp(self):
        self.app = create_hermetic_test_app()
        self.client = TestClient(self.app)

    def test_body_at_exact_limit_accepted(self):
        body = self._csp_body_of_size(5 * 1024 * 1024)
        response = self.client.post("/csp-report", content=body)
        self.assertEqual(response.status_code, 204)

    def test_body_one_byte_over_limit_rejected_with_413(self):
        body = self._csp_body_of_size(5 * 1024 * 1024 + 1)
        response = self.client.post("/csp-report", content=body)
        self.assertEqual(response.status_code, 413)
        self.assertIn("X-Content-Type-Options", response.headers)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_chunked_body_exceeding_limit_rejected_with_413(self):
        """TestClient coalesces generators into one ASGI message, but this
        still proves the 413-response wiring works end-to-end."""

        def chunks():
            yield b'{"csp-report":{"padding":"'
            yield b"x" * (5 * 1024 * 1024)
            yield b'"}}'

        response = self.client.post("/csp-report", content=chunks())
        self.assertEqual(response.status_code, 413)
        self.assertIn("X-Content-Type-Options", response.headers)

    def test_multi_chunk_accumulation_across_separate_receive_calls(self):
        """Drive the ASGI app directly with three separate receive messages
        to prove the body-limit middleware accumulates across chunks."""
        import asyncio
        from main import RequestBodyLimitMiddleware
        from starlette.types import Receive, Scope, Send

        async def run() -> bool:
            messages: list[dict] = [
                {
                    "type": "http.request",
                    "body": b'{"csp-report":{"padding":"',
                    "more_body": True,
                },
                {
                    "type": "http.request",
                    "body": b"x" * (5 * 1024 * 1024),
                    "more_body": True,
                },
                {"type": "http.request", "body": b'"}}', "more_body": False},
            ]
            downstream_called = False

            async def mock_receive() -> dict:
                return messages.pop(0)

            async def downstream(_scope: Scope, _receive: Receive, _send: Send) -> None:
                nonlocal downstream_called
                downstream_called = True

            async def send_ok(_message: dict) -> None:
                pass  # Accept any send (413 Response or normal)

            middleware = RequestBodyLimitMiddleware(
                app=downstream,  # type: ignore[arg-type]
                max_bytes=5 * 1024 * 1024,
            )
            await middleware(
                {"type": "http"},  # type: ignore[arg-type]
                mock_receive,
                send_ok,
            )
            return downstream_called

        called = asyncio.run(run())
        self.assertFalse(called, "downstream MUST NOT be called for oversized body")


class RequestTimeoutMiddlewareTests(unittest.TestCase):
    """3.3 RED — request timeout enforcement."""

    def setUp(self):
        self.app = create_hermetic_test_app()
        inner_app = self.app.app if hasattr(self.app, "app") else self.app

        @inner_app.get("/slow")
        async def slow():
            await asyncio.sleep(2)
            return {"ok": True}

        @inner_app.get("/fast")
        async def fast():
            return {"ok": True}

        self.client = TestClient(self.app)

    @patch.object(main.settings, "request_timeout_seconds", 1)
    def test_slow_route_returns_504_with_security_headers(self):
        response = self.client.get("/slow")
        self.assertEqual(response.status_code, 504)
        self.assertIn("X-Content-Type-Options", response.headers)
        self.assertEqual(response.json()["detail"], "Gateway Timeout")

    @patch.object(main.settings, "request_timeout_seconds", 1)
    def test_fast_route_returns_200(self):
        response = self.client.get("/fast")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})


class SecurityHeadersMiddlewareTests(unittest.TestCase):
    """3.5 RED — security headers on every response."""

    EXPECTED_ALWAYS_HEADERS = (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "X-XSS-Protection",
        "Referrer-Policy",
        "Content-Security-Policy-Report-Only",
    )

    def setUp(self):
        self.app = create_hermetic_test_app()
        self.client = TestClient(self.app)

    def test_success_response_includes_all_required_headers(self):
        response = self.client.get("/ping")
        self.assertEqual(response.status_code, 200)
        for header in self.EXPECTED_ALWAYS_HEADERS:
            self.assertIn(header, response.headers)

    def test_non_production_response_omits_hsts(self):
        response = self.client.get("/ping")
        self.assertNotIn("Strict-Transport-Security", response.headers)


class UnhandledExceptionSecurityTests(unittest.TestCase):
    """4.3 RED — unhandled exceptions still carry security headers."""

    EXPECTED_ALWAYS_HEADERS = (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "X-XSS-Protection",
        "Referrer-Policy",
        "Content-Security-Policy-Report-Only",
    )

    def setUp(self):
        self._debug_patcher = patch.object(main.settings, "debug", False)
        self._debug_patcher.start()
        self.addCleanup(self._debug_patcher.stop)

        self.app = create_hermetic_test_app()
        inner_app = self.app.app if hasattr(self.app, "app") else self.app

        @inner_app.get("/boom")
        async def boom():
            raise Exception("test")

        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_unhandled_exception_returns_500_with_security_headers(self):
        response = self.client.get("/boom")
        self.assertEqual(response.status_code, 500)
        for header in self.EXPECTED_ALWAYS_HEADERS:
            self.assertIn(header, response.headers)
        self.assertNotIn("Strict-Transport-Security", response.headers)

    @patch.object(main.settings, "environment", "production")
    def test_unhandled_exception_in_production_includes_hsts(self):
        from app.core.config import PRODUCTION_LIKE_ENVIRONMENTS

        self.assertIn("production", PRODUCTION_LIKE_ENVIRONMENTS)
        response = self.client.get("/boom")
        self.assertEqual(response.status_code, 500)
        self.assertIn("Strict-Transport-Security", response.headers)


class CORSOnErrorResponsesTests(unittest.TestCase):
    """P2 — CORS errors responses include CORS headers for the matching origin."""

    def setUp(self):
        self.app = create_hermetic_test_app()
        self.client = TestClient(self.app)

    def test_413_response_includes_cors_header_when_origin_matches(self):
        origin = "https://inkscroller-app.web.app"
        body = b'{"csp-report":{"padding":"' + b"x" * (5 * 1024 * 1024 + 1) + b'"}}'
        response = self.client.post(
            "/csp-report",
            content=body,
            headers={"Origin": origin},
        )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.headers.get("access-control-allow-origin"), origin)

    def test_413_response_omits_cors_header_without_origin(self):
        body = b'{"csp-report":{"padding":"' + b"x" * (5 * 1024 * 1024 + 1) + b'"}}'
        response = self.client.post("/csp-report", content=body)
        self.assertEqual(response.status_code, 413)
        self.assertNotIn("access-control-allow-origin", response.headers)

    @patch.object(main.settings, "cors_allow_credentials", True)
    def test_413_response_includes_credentials_for_specific_origin(self):
        """Credentials header is added only for specific (non-wildcard) origins."""
        with patch.dict(
            os.environ,
            {"CORS_ORIGINS": "https://inkscroller-app.web.app"},
            clear=True,
        ):
            from app.core.config import Settings

            local_settings = Settings()
        with patch.object(main.settings, "cors_origins", local_settings.cors_origins):
            origin = "https://inkscroller-app.web.app"
            body = b'{"csp-report":{"padding":"' + b"x" * (5 * 1024 * 1024 + 1) + b'"}}'
            # Recreate app with updated cors_origins for header matching
            app = create_hermetic_test_app()
            with TestClient(app) as client:
                response = client.post(
                    "/csp-report",
                    content=body,
                    headers={"Origin": origin},
                )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.headers.get("access-control-allow-origin"), origin)
        self.assertEqual(
            response.headers.get("access-control-allow-credentials"), "true"
        )


if __name__ == "__main__":
    unittest.main()
