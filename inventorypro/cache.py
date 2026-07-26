"""Bounded, thread-safe in-process cache primitives."""

from __future__ import annotations

from collections import OrderedDict, deque
from collections.abc import Callable
import threading
import time
from typing import Any


class BoundedTTLCache:
    """A small cache with expiry and deterministic least-recent eviction."""

    def __init__(self, max_entries: int = 10_000, clock: Callable[[], float] = time.monotonic):
        if max_entries < 1:
            raise ValueError("max_entries muss mindestens 1 sein.")
        self._max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            self._purge_expired()
            entry = self._entries.get(key)
            if entry is None:
                return default
            self._entries.move_to_end(key)
            return entry[1]

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            self.pop(key, None)
            return
        with self._lock:
            self._purge_expired()
            self._entries[key] = (self._clock() + ttl_seconds, value)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def pop(self, key: str, default: Any = None) -> Any:
        with self._lock:
            self._purge_expired()
            entry = self._entries.pop(key, None)
            return default if entry is None else entry[1]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            self._purge_expired()
            return len(self._entries)

    def _purge_expired(self) -> None:
        now = self._clock()
        expired = [key for key, (expires_at, _) in self._entries.items() if expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)


class SlidingWindowRateLimiter:
    """A bounded, thread-safe rate limiter for a single worker process."""

    def __init__(self, max_keys: int = 10_000, clock: Callable[[], float] = time.monotonic):
        if max_keys < 1:
            raise ValueError("max_keys muss mindestens 1 sein.")
        self._max_keys = max_keys
        self._clock = clock
        self._events: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.RLock()

    def is_limited(self, key: str, *, window_seconds: float, max_requests: int) -> bool:
        if window_seconds <= 0 or max_requests < 1:
            raise ValueError("Ungültige Rate-Limit-Konfiguration.")
        now = self._clock()
        with self._lock:
            window_start = now - window_seconds
            events = self._events.get(key, deque())
            while events and events[0] < window_start:
                events.popleft()
            if len(events) >= max_requests:
                self._store(key, events)
                return True
            events.append(now)
            self._store(key, events)
            return False

    def pop(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._events.pop(key, default)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)

    def _store(self, key: str, events: deque[float]) -> None:
        self._events[key] = events
        self._events.move_to_end(key)
        while len(self._events) > self._max_keys:
            self._events.popitem(last=False)
