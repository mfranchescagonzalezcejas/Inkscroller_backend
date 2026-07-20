"""Retry decorator with exponential backoff for upstream API calls."""

import asyncio
import logging
from collections.abc import Callable
from functools import wraps

from httpx import ConnectError, HTTPStatusError, TimeoutException

logger = logging.getLogger(__name__)

# Retry-worthy status codes (transient errors)
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# Default retry config
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 0.5  # seconds
DEFAULT_MAX_DELAY = 5.0  # seconds


def _is_retryable(
    exc: Exception,
    retryable_status_codes: frozenset[int] = RETRYABLE_STATUS_CODES,
) -> bool:
    """Check whether the exception is a transient error worth retrying.

    Transport-layer failures (timeout, connection refused) are always
    retried. HTTP errors are retried only when their status code is in
    *retryable_status_codes*, which callers may narrow from the global
    default set.
    """
    if isinstance(exc, (TimeoutException, ConnectError)):
        return True
    if isinstance(exc, HTTPStatusError):
        return exc.response.status_code in retryable_status_codes
    return False


def with_retry(
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    retryable_status_codes: frozenset[int] = RETRYABLE_STATUS_CODES,
) -> Callable:
    """Retry an async function with exponential backoff on transient errors.

    Only retries on timeouts, connection errors, and the configured HTTP
    status codes.  Passing *retryable_status_codes* lets callers narrow
    the global default (e.g. exclude 429 for MangaDex, where a 429
    escalates to an IP ban on repeated attempts).
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: object, **kwargs: object) -> object:
            last_exc: BaseException | None = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if (
                        not _is_retryable(exc, retryable_status_codes)
                        or attempt == max_retries
                    ):
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
