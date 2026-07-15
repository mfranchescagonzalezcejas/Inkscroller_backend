import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from tests.api.helpers import create_hermetic_test_app


class CSPReportTests(unittest.TestCase):
    def setUp(self):
        self.app = create_hermetic_test_app()

    def tearDown(self):
        self.app.dependency_overrides.clear()

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
            )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")

    def test_post_csp_report_accepts_application_csp_report_media_type(self):
        """Browsers send CSP reports as ``application/csp-report``, not JSON."""
        with TestClient(self.app) as client:
            response = client.post(
                "/csp-report",
                content=b'{"csp-report":{"effective-directive":"script-src"}}',
                headers={"Content-Type": "application/csp-report"},
            )

        self.assertEqual(response.status_code, 204)

    def test_post_csp_report_rejects_invalid_json(self):
        with TestClient(self.app, raise_server_exceptions=False) as client:
            response = client.post(
                "/csp-report",
                content=b"not-json",
                headers={"Content-Type": "application/csp-report"},
            )

        self.assertEqual(response.status_code, 500)

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
                response = client.post("/csp-report", json=report_payload)

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
