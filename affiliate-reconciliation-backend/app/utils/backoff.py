"""Exponential backoff helpers with jitter."""
from __future__ import annotations

import random
from typing import Optional

from app.config import BACKOFF_POLICY


def compute_backoff_seconds(attempt: int, *, base: Optional[int] = None, factor: Optional[int] = None, max_seconds: Optional[int] = None, jitter_pct: Optional[float] = None) -> float:
    """Compute exponential backoff delay with jitter."""
    if attempt < 1:
        attempt = 1
    base = int(base if base is not None else BACKOFF_POLICY["base_seconds"])  # type: ignore[index]
    factor = int(factor if factor is not None else BACKOFF_POLICY["factor"])   # type: ignore[index]
    max_seconds = int(max_seconds if max_seconds is not None else BACKOFF_POLICY["max_seconds"])  # type: ignore[index]
    jitter_pct = float(jitter_pct if jitter_pct is not None else BACKOFF_POLICY["jitter_pct"])  # type: ignore[index]

    delay = base * (factor ** (attempt - 1))
    delay = min(delay, max_seconds)
    if jitter_pct > 0:
        jitter_amount = delay * jitter_pct
        delay = random.uniform(delay - jitter_amount, delay + jitter_amount)
    return max(delay, 0.0)


__all__ = ["compute_backoff_seconds"]
