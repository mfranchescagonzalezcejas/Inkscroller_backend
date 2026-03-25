"""Retry decorator with exponential backoff for upstream API calls."""

import logging
from functools import wraps
from typing import Callable

from httpx import ConnectError, HTTPStatusError, TimeoutException

logger = logging.getLogger(__name__)

# Retry-worthy status codes (transient errors)
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# Default retry config
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 0.5  # seconds
DEFAULT_MAX_DELAY = 5.0  # seconds


def _is_retryable(exc: Exception) -> bool:
    """Determine if an exception is worth retrying."""
    if isinstance(exc, (TimeoutException, ConnectError)):
        return True
    if isinstance(exc, HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS_CODES
    return False


def with_retry(
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
) -> Callable:
    """Decorator that retries async functions with exponential backoff.

    Only retries on transient errors (timeouts, connection errors, 429/5xx).
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            import asyncio

            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if not _is_retryable(exc) or attempt == max_retries:
                        raise

                    delay = min(base_delay * (2**attempt), max_delay)
                    logger.warning(
                        "Retry %d/%d for %s after %.1fs (%s)",
                        attempt + 1,
                        max_retries,
                        func.__qualname__,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)

            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator
