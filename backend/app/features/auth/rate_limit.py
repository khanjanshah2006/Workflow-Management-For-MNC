"""Sliding-window rate limit for the login endpoints (S9-BE-4).

The limiter is in-memory and per process. It does not cover multiple workers or
instances; a shared store such as Redis would be needed for that.

Buckets are keyed on request.client.host. Behind a reverse proxy (e.g. Render), run
uvicorn with --proxy-headers and FORWARDED_ALLOW_IPS (or --forwarded-allow-ips) set to
trust the proxy; otherwise client.host is the proxy's IP and all users share one bucket.
"""
import math
import threading
import time
from collections import deque
from typing import Optional

from fastapi import HTTPException, Request, status

LOGIN_RATE_LIMIT = 20
LOGIN_RATE_WINDOW_SECONDS = 60
# Every N checks, drop keys with no hits inside the window so idle IPs don't accumulate.
SWEEP_EVERY = 1000


class SlidingWindowLimiter:
    """Allow at most ``limit`` hits per key within the last ``window_seconds``."""

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[tuple, deque] = {}
        self._checks = 0
        self._lock = threading.Lock()

    def check(self, key: tuple) -> Optional[int]:
        """Record a hit and return None if allowed, else seconds until a slot frees."""
        now = time.monotonic()
        with self._lock:
            self._checks += 1
            if self._checks % SWEEP_EVERY == 0:
                self._sweep(now)
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.window_seconds:
                hits.popleft()
            if len(hits) >= self.limit:
                return max(1, math.ceil(hits[0] + self.window_seconds - now))
            hits.append(now)
            return None

    def _sweep(self, now: float) -> None:
        """Drop keys whose newest hit is outside the window. Caller holds the lock."""
        cutoff = now - self.window_seconds
        stale = [key for key, hits in self._hits.items() if not hits or hits[-1] <= cutoff]
        for key in stale:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


login_limiter = SlidingWindowLimiter(LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW_SECONDS)


def login_rate_limit(request: Request) -> None:
    """FastAPI dependency: throttle login attempts per path and client IP."""
    ip = request.client.host if request.client else "unknown"
    retry_after = login_limiter.check((request.url.path, ip))
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again in a minute.",
            headers={"Retry-After": str(retry_after)},
        )
