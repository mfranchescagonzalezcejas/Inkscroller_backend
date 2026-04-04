"""Firebase Admin SDK bootstrap and token-verification helper.

Provides `verify_firebase_token()` which accepts a raw Bearer token string
and returns a `FirebaseTokenPayload` on success, or raises an
`AuthenticationError` for any invalid/expired/missing token.
"""

import logging
from dataclasses import dataclass

import firebase_admin
from firebase_admin import auth as firebase_auth_sdk
from firebase_admin import credentials

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FirebaseTokenPayload:
    """Decoded claims extracted from a verified Firebase ID token."""

    uid: str
    email: str
    display_name: str | None = None


class AuthenticationError(Exception):
    """Raised when a Firebase token is missing, malformed, or invalid."""


def init_firebase_admin() -> None:
    """Initialize the Firebase Admin SDK if not already initialized.

    When ``GOOGLE_APPLICATION_CREDENTIALS`` env var points to a service-account
    JSON file, ``firebase_admin`` picks it up automatically via
    ``credentials.ApplicationDefault()``.  For local development without a
    service-account file, set ``FIREBASE_PROJECT_ID`` in ``.env`` and launch
    the Firebase Auth emulator; token verification will be skipped by the SDK
    when ``FIREBASE_AUTH_EMULATOR_HOST`` is set.

    If no credentials are available at all (e.g., CI / unit-test environment)
    the function logs a warning and continues — calls to ``verify_firebase_token``
    will fail with ``AuthenticationError`` at that point, which test overrides
    of ``get_current_user`` prevent from ever being reached.
    """
    if firebase_admin._apps:
        # Already initialized (e.g., hot-reload or test re-entry).
        return

    if not settings.firebase_project_id:
        logger.warning(
            "FIREBASE_PROJECT_ID is not set — Firebase Admin SDK not initialized. "
            "Protected endpoints will reject all requests."
        )
        return

    try:
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {"projectId": settings.firebase_project_id})
        logger.info(
            "Firebase Admin SDK initialized (project: %s)", settings.firebase_project_id
        )
    except Exception as exc:
        logger.warning(
            "Firebase Admin SDK initialization failed (%s). "
            "Protected endpoints will reject all requests.",
            exc,
        )


async def verify_firebase_token(token: str) -> FirebaseTokenPayload:
    """Verify a Firebase ID token and return its decoded claims.

    Args:
        token: Raw ID token string (without the `Bearer ` prefix).

    Returns:
        A :class:FirebaseTokenPayload with `uid`, `email`, and optional
        `display_name` extracted from the verified claims.

    Raises:
        :class:AuthenticationError: If the token is empty, expired, or fails
            Firebase verification.
    """
    if not token:
        raise AuthenticationError("No authentication token provided.")

    try:
        decoded = firebase_auth_sdk.verify_id_token(token)
    except firebase_auth_sdk.ExpiredIdTokenError:
        raise AuthenticationError("Firebase ID token has expired.")
    except firebase_auth_sdk.RevokedIdTokenError:
        raise AuthenticationError("Firebase ID token has been revoked.")
    except firebase_auth_sdk.InvalidIdTokenError as exc:
        raise AuthenticationError(f"Invalid Firebase ID token: {exc}") from exc
    except Exception as exc:
        logger.error("Unexpected error verifying Firebase token: %s", exc)
        raise AuthenticationError("Token verification failed.") from exc

    uid: str = decoded.get("uid", "")
    email: str = decoded.get("email", "")
    display_name: str | None = decoded.get("name")

    if not uid or not email:
        raise AuthenticationError(
            "Firebase token missing required claims (uid, email)."
        )

    return FirebaseTokenPayload(uid=uid, email=email, display_name=display_name)
