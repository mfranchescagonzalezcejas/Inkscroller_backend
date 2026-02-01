import time
from typing import Any


class SimpleCache:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if not item:
            return None

        expires_at, value = item
        if time.time() > expires_at:
            del self._store[key]
            return None

        return value

    def set(self, key: str, value: Any) -> None:
        expires_at = time.time() + self.ttl
        self._store[key] = (expires_at, value)
