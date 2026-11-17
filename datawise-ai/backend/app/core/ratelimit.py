"""In-process token bucket per (user, route).

Limitation (documented): state lives in this process only, so it is not shared across replicas.
"""

import threading
import time
from dataclasses import dataclass


@dataclass
class _Bucket:
    tokens: float
    updated: float


class TokenBucketLimiter:
    def __init__(self, capacity: int, refill_per_second: float) -> None:
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            b = self._buckets.get(key)
            if b is None:
                b = _Bucket(tokens=float(self.capacity), updated=now)
                self._buckets[key] = b
            b.tokens = min(self.capacity, b.tokens + (now - b.updated) * self.refill_per_second)
            b.updated = now
            if b.tokens >= 1:
                b.tokens -= 1
                return True
            return False

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()
