"""Global exception handlers for consistent API error responses."""

import logging

from app.core.config import settings
from app.core.security_headers import get_security_headers
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ConnectError, HTTPStatusError, TimeoutException

logger = logging.getLogger(__name__)


class UpstreamServiceError(Exception):
    """Raised when an external API (MangaDex/Jikan) returns an unexpected error."""

    def __init__(self, service: str, detail: str = ""):
        """Initialise with upstream service name and optional detail message."""
        self.service = service
        self.detail = detail
        super().__init__(f"{service}: {detail}")


def _error_response(status_code: int, error: str, detail: str) -> JSONResponse:
    """Build a standardised JSON error response with the given status, code, and detail."""
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "detail": detail},
    )


async def handle_http_status_error(
    request: Request, exc: HTTPStatusError
) -> JSONResponse:
    """Translate upstream HTTP errors (4xx/5xx) into standard API error responses."""
    upstream_status = exc.response.status_code
    url = str(exc.request.url)
    logger.error("Upstream HTTP %d from %s", upstream_status, url)

    if upstream_status == 404:
        return _error_response(
            404, "not_found", "The requested resource was not found upstream."
        )
    if upstream_status == 429:
        return _error_response(
            503, "rate_limited", "Upstream API rate limit exceeded. Please retry later."
        )
    return _error_response(
        502, "upstream_error", f"Upstream service returned HTTP {upstream_status}."
    )


async def handle_timeout(request: Request, exc: TimeoutException) -> JSONResponse:
    """Return a 504 Gateway Timeout when an upstream API does not respond in time."""
    logger.error("Upstream timeout: %s", exc)
    return _error_response(504, "timeout", "Upstream service did not respond in time.")


async def handle_connect_error(request: Request, exc: ConnectError) -> JSONResponse:
    """Return a 502 Bad Gateway when the backend cannot reach an upstream API."""
    logger.error("Upstream connection failed: %s", exc)
    return _error_response(
        502, "connection_error", "Could not connect to upstream service."
    )


async def handle_upstream_service_error(
    request: Request, exc: UpstreamServiceError
) -> JSONResponse:
    """Return a 502 for application-level upstream errors (e.g. Firebase Auth failure)."""
    logger.error("UpstreamServiceError [%s]: %s", exc.service, exc.detail)
    return _error_response(
        502, "upstream_error", f"Error from {exc.service}: {exc.detail}"
    )


async def handle_unhandled(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler that returns a 500 for any unhandled exception."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    response = _error_response(500, "internal_error", "An unexpected error occurred.")
    response.headers.update(get_security_headers(settings.is_production_like()))
    return response


class AuthError(Exception):
    """Raised when a request fails authentication or authorization."""

    def __init__(self, detail: str = "Authentication required."):
        """Initialise with an optional detail message (default: "Authentication required.")."""
        self.detail = detail
        super().__init__(detail)


class PreferencesValidationError(Exception):
    """Raised when a preferences update payload is invalid."""

    def __init__(self, detail: str = "Invalid preferences payload."):
        """Initialise with an optional detail message (default: "Invalid preferences payload.")."""
        self.detail = detail
        super().__init__(detail)


class ProfileConflictError(Exception):
    """Raised when profile metadata conflicts with another account."""

    def __init__(self, detail: str = "Profile metadata conflict."):
        """Initialise with an optional detail message (default: "Profile metadata conflict.")."""
        self.detail = detail
        super().__init__(detail)


async def handle_auth_error(request: Request, exc: AuthError) -> JSONResponse:
    """Return a 401 response for authentication and authorization failures."""
    logger.warning(
        "Auth error on %s %s: %s", request.method, request.url.path, exc.detail
    )
    return _error_response(401, "authentication_error", exc.detail)


async def handle_preferences_validation_error(
    request: Request, exc: PreferencesValidationError
) -> JSONResponse:
    """Return a 422 response for invalid preferences payloads."""
    logger.warning("Preferences validation error: %s", exc.detail)
    return _error_response(422, "validation_error", exc.detail)


async def handle_profile_conflict_error(
    request: Request, exc: ProfileConflictError
) -> JSONResponse:
    """Return a 409 response for profile conflicts (e.g. username taken)."""
    logger.warning("Profile conflict: %s", exc.detail)
    return _error_response(409, "profile_conflict", exc.detail)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI app."""
    # ponytail: Starlette's add_exception_handler expects Exception-typed
    # callables but each handler is intentionally narrowed to a specific
    # exception subclass. The runtime contract is correct; mypy can't
    # prove the contravariance through this dispatcher.
    app.add_exception_handler(HTTPStatusError, handle_http_status_error)  # type: ignore[arg-type]
    app.add_exception_handler(TimeoutException, handle_timeout)  # type: ignore[arg-type]
    app.add_exception_handler(ConnectError, handle_connect_error)  # type: ignore[arg-type]
    app.add_exception_handler(UpstreamServiceError, handle_upstream_service_error)  # type: ignore[arg-type]
    app.add_exception_handler(AuthError, handle_auth_error)  # type: ignore[arg-type]
    app.add_exception_handler(
        PreferencesValidationError,
        handle_preferences_validation_error,  # type: ignore[arg-type]
    )
    app.add_exception_handler(ProfileConflictError, handle_profile_conflict_error)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, handle_unhandled)
