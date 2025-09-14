"""In-memory rate limiter utilities.

Implements a lightweight fixed-window + burst allowance mechanism suitable for
single-process test environments. For production horizontal scaling replace
with Redis or another distributed store (keeping same interface) and consider
sliding window or token bucket algorithms.

Usage pattern:
    from app.utils.ratelimiter import rate_limiter, RateLimitCategory
    allowed, state = rate_limiter.check_and_increment(
        key=api_key,
        category="submission",  # or "default"
        limit=100,
        window_seconds=3600,
    )

The RateLimiter stores per-key windows: { key: { window_start: int, count: int } }
Thread-safety: uses an asyncio.Lock per key bucket for minimal contention.

Headers contract (mirrors common conventions):
    X-RateLimit-Limit: int total allowed in the window
    X-RateLimit-Remaining: int remaining
    X-RateLimit-Reset: epoch seconds when current window resets

Return semantics:
    check_and_increment -> (allowed: bool, meta: dict)
        meta = {
            'limit': int,
            'remaining': int,
            'reset_epoch': int,
            'window_start': int,
            'count': int
        }

Design notes:
 - Fixed window chosen for simplicity & test determinism.
 - Small optimization: maintain monotonic time via time.time() (acceptable here).
 - Lock granularity per key to prevent global blocking.
 - Optional burst support can be added by allowing count exceed limit within
   small grace range; omitted for clarity.
"""
from __future__ import annotations

import time
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Tuple

@dataclass
class Bucket:
    window_start: int
    count: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

class InMemoryRateLimiter:
    def __init__(self):
        # key -> category -> Bucket
        self._buckets: Dict[str, Dict[str, Bucket]] = {}
        self._global_lock = asyncio.Lock()

    def _now(self) -> int:
        return int(time.time())

    async def check_and_increment(self, key: str, category: str, limit: int, window_seconds: int) -> Tuple[bool, dict]:
        now = self._now()
        window_start = now - (now % window_seconds)  # fixed window boundary

        # Fast path if buckets exist; else create under global lock
        buckets = self._buckets.get(key)
        if buckets is None:
            async with self._global_lock:
                buckets = self._buckets.setdefault(key, {})
        bucket = buckets.get(category)
        if bucket is None:
            async with self._global_lock:
                # Re-check inside lock
                bucket = buckets.get(category)
                if bucket is None:
                    bucket = Bucket(window_start=window_start)
                    buckets[category] = bucket

        async with bucket.lock:
            # Reset window if expired
            if bucket.window_start != window_start:
                bucket.window_start = window_start
                bucket.count = 0
            bucket.count += 1
            allowed = bucket.count <= limit
            remaining = max(0, limit - bucket.count)
            reset_epoch = bucket.window_start + window_seconds
            meta = {
                "limit": limit,
                "remaining": remaining if allowed else 0,
                "reset_epoch": reset_epoch,
                "window_start": bucket.window_start,
                "count": bucket.count,
                "category": category,
            }
            return allowed, meta

    async def get_state(self, key: str, category: str, limit: int, window_seconds: int) -> dict:
        now = self._now()
        window_start = now - (now % window_seconds)
        buckets = self._buckets.get(key)
        if not buckets or category not in buckets:
            reset_epoch = window_start + window_seconds
            return {"limit": limit, "remaining": limit, "reset_epoch": reset_epoch, "count": 0, "category": category}
        bucket = buckets[category]
        if bucket.window_start != window_start:
            # Window would reset on next increment; treat as empty
            reset_epoch = window_start + window_seconds
            return {"limit": limit, "remaining": limit, "reset_epoch": reset_epoch, "count": 0, "category": category}
        reset_epoch = bucket.window_start + window_seconds
        remaining = max(0, limit - bucket.count)
        return {"limit": limit, "remaining": remaining, "reset_epoch": reset_epoch, "count": bucket.count, "category": category}

# Singleton instance used application-wide
rate_limiter = InMemoryRateLimiter()

__all__ = ["rate_limiter", "InMemoryRateLimiter"]
