"""Global exception handlers for consistent API error responses."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ConnectError, HTTPStatusError, TimeoutException

logger = logging.getLogger(__name__)


class UpstreamServiceError(Exception):
    """Raised when an external API (MangaDex/Jikan) returns an unexpected error."""

    def __init__(self, service: str, detail: str = ""):
        self.service = service
        self.detail = detail
        super().__init__(f"{service}: {detail}")


def _error_response(status_code: int, error: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "detail": detail},
    )


async def handle_http_status_error(
    request: Request, exc: HTTPStatusError
) -> JSONResponse:
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
    logger.error("Upstream timeout: %s", exc)
    return _error_response(504, "timeout", "Upstream service did not respond in time.")


async def handle_connect_error(request: Request, exc: ConnectError) -> JSONResponse:
    logger.error("Upstream connection failed: %s", exc)
    return _error_response(
        502, "connection_error", "Could not connect to upstream service."
    )


async def handle_upstream_service_error(
    request: Request, exc: UpstreamServiceError
) -> JSONResponse:
    logger.error("UpstreamServiceError [%s]: %s", exc.service, exc.detail)
    return _error_response(
        502, "upstream_error", f"Error from {exc.service}: {exc.detail}"
    )


async def handle_unhandled(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return _error_response(500, "internal_error", "An unexpected error occurred.")


class AuthError(Exception):
    """Raised when a request fails authentication or authorization."""

    def __init__(self, detail: str = "Authentication required."):
        self.detail = detail
        super().__init__(detail)


class PreferencesValidationError(Exception):
    """Raised when a preferences update payload is invalid."""

    def __init__(self, detail: str = "Invalid preferences payload."):
        self.detail = detail
        super().__init__(detail)


async def handle_auth_error(request: Request, exc: AuthError) -> JSONResponse:
    logger.warning(
        "Auth error on %s %s: %s", request.method, request.url.path, exc.detail
    )
    return _error_response(401, "authentication_error", exc.detail)


async def handle_preferences_validation_error(
    request: Request, exc: PreferencesValidationError
) -> JSONResponse:
    logger.warning("Preferences validation error: %s", exc.detail)
    return _error_response(422, "validation_error", exc.detail)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI app."""
    app.add_exception_handler(HTTPStatusError, handle_http_status_error)
    app.add_exception_handler(TimeoutException, handle_timeout)
    app.add_exception_handler(ConnectError, handle_connect_error)
    app.add_exception_handler(UpstreamServiceError, handle_upstream_service_error)
    app.add_exception_handler(AuthError, handle_auth_error)
    app.add_exception_handler(
        PreferencesValidationError, handle_preferences_validation_error
    )
    app.add_exception_handler(Exception, handle_unhandled)
