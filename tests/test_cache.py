import threading
from unittest import TestCase

from inventorypro.cache import BoundedTTLCache, SlidingWindowRateLimiter


class CacheTestCase(TestCase):
    def test_ttl_cache_expires_and_evicts_least_recent_values(self):
        current_time = [0.0]
        cache = BoundedTTLCache(max_entries=2, clock=lambda: current_time[0])
        cache.set("first", "a", 10)
        cache.set("second", "b", 10)
        self.assertEqual(cache.get("first"), "a")
        cache.set("third", "c", 10)
        self.assertIsNone(cache.get("second"))
        self.assertEqual(cache.get("first"), "a")
        current_time[0] = 10.0
        self.assertIsNone(cache.get("first"))
        self.assertEqual(len(cache), 0)
        cache.set("temporary", "value", 10)
        self.assertEqual(cache.pop("temporary"), "value")
        self.assertEqual(cache.pop("missing", "fallback"), "fallback")
        cache.set("clearable", "value", 10)
        cache.set("expired", "value", 0)
        cache.clear()
        self.assertEqual(len(cache), 0)

    def test_rate_limiter_enforces_windows_and_bounds_keys(self):
        current_time = [0.0]
        limiter = SlidingWindowRateLimiter(max_keys=2, clock=lambda: current_time[0])
        self.assertFalse(limiter.is_limited("user", window_seconds=10, max_requests=2))
        self.assertFalse(limiter.is_limited("user", window_seconds=10, max_requests=2))
        self.assertTrue(limiter.is_limited("user", window_seconds=10, max_requests=2))
        current_time[0] = 10.1
        self.assertFalse(limiter.is_limited("user", window_seconds=10, max_requests=2))
        limiter.is_limited("other", window_seconds=10, max_requests=1)
        limiter.is_limited("third", window_seconds=10, max_requests=1)
        self.assertEqual(len(limiter), 2)
        self.assertIsNotNone(limiter.pop("third"))
        self.assertIsNone(limiter.pop("missing"))
        limiter.clear()
        self.assertEqual(len(limiter), 0)

    def test_rate_limiter_is_thread_safe_for_a_shared_key(self):
        limiter = SlidingWindowRateLimiter()
        start = threading.Barrier(20)
        results = []
        results_lock = threading.Lock()

        def attempt():
            start.wait()
            limited = limiter.is_limited("shared", window_seconds=60, max_requests=3)
            with results_lock:
                results.append(limited)

        workers = [threading.Thread(target=attempt) for _ in range(20)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(results.count(False), 3)
        self.assertEqual(results.count(True), 17)

    def test_invalid_cache_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            BoundedTTLCache(max_entries=0)
        with self.assertRaises(ValueError):
            SlidingWindowRateLimiter(max_keys=0)
        with self.assertRaises(ValueError):
            SlidingWindowRateLimiter().is_limited("key", window_seconds=0, max_requests=1)
