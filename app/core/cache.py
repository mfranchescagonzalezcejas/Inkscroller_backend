"""Simple in-memory cache with TTL-based expiry."""

import time
from typing import Any


class SimpleCache:
    """In-memory dict-based cache with TTL expiry per entry."""

    def __init__(self, ttl_seconds: int = 300):
        """Initialise with a default TTL in seconds (default 300)."""
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        """Return cached value for ``key``, or ``None`` if expired or missing."""
        item = self._store.get(key)
        if not item:
            return None

        expires_at, value = item
        if time.time() > expires_at:
            del self._store[key]
            return None

        return value

    def set(self, key: str, value: Any) -> None:
        """Store ``value`` under ``key`` with the configured TTL."""
        expires_at = time.time() + self.ttl
        self._store[key] = (expires_at, value)
