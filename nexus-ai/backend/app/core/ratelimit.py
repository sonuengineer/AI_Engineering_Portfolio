"""In-process token-bucket rate limiter.

Limitation (documented): state is per process, so limits are not shared across replicas.
A Redis-backed implementation would be the production upgrade path.
"""

import threading
import time

from app.core.errors import RateLimited


class TokenBucketLimiter:
    def __init__(self, per_minute: int):
        self.capacity = float(per_minute)
        self.refill_per_s = per_minute / 60.0
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, cost: float = 1.0) -> None:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(key, (self.capacity, now))
            tokens = min(self.capacity, tokens + (now - last) * self.refill_per_s)
            if tokens < cost:
                self._buckets[key] = (tokens, now)
                raise RateLimited("Rate limit exceeded; retry shortly")
            self._buckets[key] = (tokens - cost, now)
