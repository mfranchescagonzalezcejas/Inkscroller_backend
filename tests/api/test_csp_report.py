import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from tests.api.helpers import create_hermetic_test_app


class CSPReportTests(unittest.TestCase):
    def setUp(self):
        self.app = create_hermetic_test_app()
        self._trusted_origin = "https://inkscroller-app.web.app"

    def tearDown(self):
        self.app.dependency_overrides.clear()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _headers(self, origin: str | None = None) -> dict[str, str]:
        h: dict[str, str] = {}
        if origin:
            h["Origin"] = origin
        return h

    # ── tests ────────────────────────────────────────────────────────────────

    def test_post_csp_report_returns_204(self):
        with TestClient(self.app) as client:
            response = client.post(
                "/csp-report",
                json={
                    "csp-report": {
                        "effective-directive": "script-src",
                        "violated-directive": "script-src",
                        "disposition": "report",
                        "status-code": 200,
                        "line-number": 42,
                        "column-number": 7,
                    }
                },
                headers=self._headers(self._trusted_origin),
            )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")

    def test_post_csp_report_accepts_application_csp_report_media_type(self):
        """Browsers send CSP reports as ``application/csp-report``, not JSON."""
        with TestClient(self.app) as client:
            response = client.post(
                "/csp-report",
                content=b'{"csp-report":{"effective-directive":"script-src"}}',
                headers={
                    "Content-Type": "application/csp-report",
                    "Origin": self._trusted_origin,
                },
            )

        self.assertEqual(response.status_code, 204)

    def test_post_csp_report_rejects_requests_from_untrusted_origins(self):
        """CSP reports from unknown origins must be silently discarded."""
        with TestClient(self.app) as client:
            response = client.post(
                "/csp-report",
                json={"csp-report": {"effective-directive": "script-src"}},
                headers=self._headers("https://evil.com"),
            )
        self.assertEqual(response.status_code, 204)

    def test_post_csp_report_sanitizes_field_values(self):
        """Values with newlines or >200 chars are truncated/cleaned."""
        with patch("app.api.security.logger") as mock_logger:
            with TestClient(self.app) as client:
                response = client.post(
                    "/csp-report",
                    json={
                        "csp-report": {
                            "effective-directive": "script-src https://evil.com\n<script>alert(1)</script>",
                            "violated-directive": "x" * 500,
                        }
                    },
                    headers=self._headers(self._trusted_origin),
                )

        self.assertEqual(response.status_code, 204)
        logged_output = " ".join(
            str(call.args) + " " + str(call.kwargs)
            for call in mock_logger.info.call_args_list
        )
        # Newline in value must be replaced with space
        self.assertNotIn("\\n", logged_output)
        # Long value must be truncated to 200 chars
        self.assertNotIn("x" * 300, logged_output)
        self.assertIn("x" * 200, logged_output)

    def test_post_csp_report_rejects_invalid_json(self):
        with TestClient(self.app) as client:
            response = client.post(
                "/csp-report",
                content=b"not-json",
                headers={
                    "Content-Type": "application/csp-report",
                    "Origin": self._trusted_origin,
                },
            )

        self.assertEqual(response.status_code, 204)

    def test_post_csp_report_does_not_log_url_fields(self):
        report_payload = {
            "csp-report": {
                "document-uri": "https://example.com/secret?page=1",
                "referrer": "https://evil.example.com",
                "blocked-uri": "https://tracker.example.com/pixel.js",
                "effective-directive": "script-src",
                "violated-directive": "script-src",
                "disposition": "report",
                "status-code": 200,
                "line-number": 42,
                "column-number": 7,
            }
        }

        with patch("app.api.security.logger") as mock_logger:
            with TestClient(self.app) as client:
                response = client.post(
                    "/csp-report",
                    json=report_payload,
                    headers=self._headers(self._trusted_origin),
                )

        self.assertEqual(response.status_code, 204)

        logged_output = " ".join(
            str(call.args) + " " + str(call.kwargs)
            for call in mock_logger.info.call_args_list
        )
        self.assertNotIn("https://example.com/secret?page=1", logged_output)
        self.assertNotIn("https://evil.example.com", logged_output)
        self.assertNotIn("https://tracker.example.com/pixel.js", logged_output)
        self.assertNotIn("document-uri", logged_output)
        self.assertNotIn("referrer", logged_output)
        self.assertNotIn("blocked-uri", logged_output)


if __name__ == "__main__":
    unittest.main()
