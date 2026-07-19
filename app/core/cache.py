"""Simple in-memory cache with LRU eviction and TTL-based expiry."""

import time
from collections import OrderedDict
from typing import Any


class SimpleCache:
    """In-memory dict-based cache with LRU eviction and TTL expiry per entry.

    When the cache exceeds *maxsize*, the least-recently-used entry is
    evicted regardless of whether it has expired.  Expired entries are
    purged on access.
    """

    def __init__(self, ttl_seconds: int = 300, maxsize: int = 1000):
        """Initialise with a default TTL in seconds and maximum entry count."""
        self.ttl = ttl_seconds
        self.maxsize = maxsize
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def get(self, key: str) -> Any | None:
        """Return cached value for ``key``, or ``None`` if expired or missing."""
        item = self._store.get(key)
        if not item:
            return None

        expires_at, value = item
        if time.time() > expires_at:
            del self._store[key]
            return None

        # LRU: move to end (most-recently-used)
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        """Store ``value`` under ``key`` with the configured TTL."""
        expires_at = time.time() + self.ttl
        self._store[key] = (expires_at, value)
        # LRU: move to end on set too
        self._store.move_to_end(key)
        if len(self._store) > self.maxsize:
            self._store.popitem(last=False)  # evict least-recently-used
