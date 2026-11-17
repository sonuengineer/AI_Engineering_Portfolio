"""In-process token bucket rate limiter keyed by user+route.

Documented limitation: state is per process, so limits are not shared across replicas.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class _Bucket:
    tokens: float
    updated: float


class TokenBucketLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, per_minute: int) -> bool:
        capacity = float(per_minute)
        rate = capacity / 60.0
        now = time.monotonic()
        with self._lock:
            b = self._buckets.get(key)
            if b is None:
                b = _Bucket(tokens=capacity, updated=now)
                self._buckets[key] = b
            b.tokens = min(capacity, b.tokens + (now - b.updated) * rate)
            b.updated = now
            if b.tokens >= 1.0:
                b.tokens -= 1.0
                return True
            return False

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


limiter = TokenBucketLimiter()
