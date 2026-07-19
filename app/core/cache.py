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
        """Store ``value`` under ``key`` with the configured TTL.

        Purges expired entries first (cheap).  If still over *maxsize*,
        evicts the least-recently-used entry.
        """
        expires_at = time.time() + self.ttl
        self._store[key] = (expires_at, value)
        self._store.move_to_end(key)
        if len(self._store) > self.maxsize:
            # Purge expired entries first (scan full store)
            now = time.time()
            for k in list(self._store.keys()):
                if now > self._store[k][0]:
                    del self._store[k]
            # Still over limit → evict LRU
            while len(self._store) > self.maxsize:
                self._store.popitem(last=False)
