"""Tests for the Firebase token-verification path in the real dependency chain.

Strategy
--------
These tests patch ``firebase_admin.auth.verify_id_token`` at the SDK boundary
rather than overriding ``get_current_user`` wholesale.  This exercises the
real ``get_current_user`` code path (Bearer-scheme extraction → call to
``verify_firebase_token`` → bootstrap user via ``UserService``) and confirms
that the correct error-shape is produced by the registered ``AuthError``
handler.

An in-memory SQLite DB is still used via ``get_db`` so tests stay hermetic.
"""

import asyncio
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.database import init_db
from app.core.db_adapter import DatabaseAdapter
from app.core.dependencies import get_db
from main import create_app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_DECODED_TOKEN = {
    "uid": "patched-uid-001",
    "email": "patched@example.com",
    "name": "Patched User",
}


async def _make_test_db() -> DatabaseAdapter:
    """Create an in-memory SQLite DB using the real production DDL via init_db."""
    return await init_db(":memory:")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class FirebaseTokenVerificationPathTests(unittest.TestCase):
    """Exercises ``get_current_user`` through the real verification path."""

    def setUp(self):
        self.app = create_app()
        self.db = asyncio.get_event_loop().run_until_complete(_make_test_db())
        self.app.dependency_overrides[get_db] = lambda: self.db

    def tearDown(self):
        self.app.dependency_overrides.clear()
        asyncio.get_event_loop().run_until_complete(self.db.close())

    # ------------------------------------------------------------------
    # Happy path: SDK returns a valid decoded token
    # ------------------------------------------------------------------

    def test_valid_token_bootstraps_user_and_returns_200(self):
        """Patching ``verify_id_token`` so it returns valid claims.

        The real ``get_current_user`` path runs:
          1. HTTPBearer extracts the bearer token.
          2. ``verify_firebase_token`` calls ``firebase_auth_sdk.verify_id_token``.
          3. The mock returns ``_FAKE_DECODED_TOKEN``.
          4. ``UserService.get_or_create_user`` bootstraps the DB row.
          5. The endpoint returns 200 with the user payload.
        """
        with patch(
            "app.core.firebase_auth.firebase_auth_sdk.verify_id_token",
            return_value=_FAKE_DECODED_TOKEN,
        ):
            with TestClient(self.app) as client:
                response = client.get(
                    "/users/me",
                    headers={"Authorization": "Bearer any-valid-looking-token"},
                )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["firebase_uid"], _FAKE_DECODED_TOKEN["uid"])
        self.assertEqual(data["email"], _FAKE_DECODED_TOKEN["email"])

    def test_valid_token_second_request_returns_same_user(self):
        """Second call with same patched token finds existing user row (idempotent)."""
        with patch(
            "app.core.firebase_auth.firebase_auth_sdk.verify_id_token",
            return_value=_FAKE_DECODED_TOKEN,
        ):
            with TestClient(self.app) as client:
                client.get(
                    "/users/me",
                    headers={"Authorization": "Bearer any-valid-looking-token"},
                )
                response = client.get(
                    "/users/me",
                    headers={"Authorization": "Bearer any-valid-looking-token"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["firebase_uid"], _FAKE_DECODED_TOKEN["uid"])

    # ------------------------------------------------------------------
    # Error paths: SDK raises standard Firebase exceptions
    # ------------------------------------------------------------------

    def test_expired_token_returns_401_authentication_error_shape(self):
        """Expired ID token → ``AuthError`` handler → 401 with standard shape."""
        from firebase_admin.auth import ExpiredIdTokenError

        with patch(
            "app.core.firebase_auth.firebase_auth_sdk.verify_id_token",
            side_effect=ExpiredIdTokenError("token expired", cause=None),
        ):
            with TestClient(self.app) as client:
                response = client.get(
                    "/users/me",
                    headers={"Authorization": "Bearer expired-token"},
                )

        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertEqual(body["error"], "authentication_error")
        self.assertIn("expired", body["detail"].lower())

    def test_invalid_token_returns_401_authentication_error_shape(self):
        """Malformed / invalid token → 401 with ``authentication_error`` shape."""
        from firebase_admin.auth import InvalidIdTokenError

        with patch(
            "app.core.firebase_auth.firebase_auth_sdk.verify_id_token",
            side_effect=InvalidIdTokenError("bad token"),
        ):
            with TestClient(self.app) as client:
                response = client.get(
                    "/users/me",
                    headers={"Authorization": "Bearer malformed-token"},
                )

        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertEqual(body["error"], "authentication_error")

    def test_unexpected_sdk_exception_returns_401(self):
        """An unexpected exception from the SDK is caught and produces a 401."""
        with patch(
            "app.core.firebase_auth.firebase_auth_sdk.verify_id_token",
            side_effect=RuntimeError("SDK blew up"),
        ):
            with TestClient(self.app) as client:
                response = client.get(
                    "/users/me",
                    headers={"Authorization": "Bearer some-token"},
                )

        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertEqual(body["error"], "authentication_error")

    def test_missing_token_still_returns_401_without_patching(self):
        """No Authorization header → 401 before even reaching ``verify_id_token``."""
        with TestClient(self.app) as client:
            response = client.get("/users/me")

        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertEqual(body["error"], "authentication_error")

    # ------------------------------------------------------------------
    # Token claims validation
    # ------------------------------------------------------------------

    def test_token_missing_uid_returns_401(self):
        """A token that decodes but lacks ``uid`` is rejected by our claim check."""
        incomplete_claims = {"email": "no-uid@example.com"}  # no "uid" key

        with patch(
            "app.core.firebase_auth.firebase_auth_sdk.verify_id_token",
            return_value=incomplete_claims,
        ):
            with TestClient(self.app) as client:
                response = client.get(
                    "/users/me",
                    headers={"Authorization": "Bearer incomplete-token"},
                )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "authentication_error")

    def test_token_missing_email_returns_401(self):
        """A token that decodes but lacks ``email`` is rejected by our claim check."""
        incomplete_claims = {"uid": "some-uid"}  # no "email" key

        with patch(
            "app.core.firebase_auth.firebase_auth_sdk.verify_id_token",
            return_value=incomplete_claims,
        ):
            with TestClient(self.app) as client:
                response = client.get(
                    "/users/me",
                    headers={"Authorization": "Bearer incomplete-token"},
                )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "authentication_error")


if __name__ == "__main__":
    unittest.main()
