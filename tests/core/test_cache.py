import time
import unittest

from app.core.cache import SimpleCache


class TestSimpleCacheMaxsize(unittest.TestCase):
    def test_evicts_expired_entry_before_oldest_live_entry(self):
        cache = SimpleCache(maxsize=2)
        cache._store = {
            "oldest-live": (time.time() + 60, "live"),
            "expired": (time.time() - 1, "stale"),
        }

        cache.set("new", "value")

        self.assertEqual(cache.get("oldest-live"), "live")
        self.assertIsNone(cache.get("expired"))
        self.assertEqual(cache.get("new"), "value")

    def test_evicts_oldest_entry_when_none_are_expired(self):
        cache = SimpleCache(maxsize=2)
        cache.set("first", 1)
        cache.set("second", 2)
        cache.set("third", 3)

        self.assertIsNone(cache.get("first"))
        self.assertEqual(cache.get("second"), 2)
        self.assertEqual(cache.get("third"), 3)
