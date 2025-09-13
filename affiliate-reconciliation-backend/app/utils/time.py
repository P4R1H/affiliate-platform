"""Time utilities (UTC now, elapsed formatting)."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def format_elapsed(start: datetime, end: datetime | None = None) -> str:
    end_ts = end or utc_now()
    delta: timedelta = end_ts - start
    ms = int(delta.total_seconds() * 1000)
    if ms < 1000:
        return f"{ms}ms"
    if ms < 60_000:
        return f"{ms/1000:.2f}s"
    return f"{delta.total_seconds()/60:.2f}m"

__all__ = ["utc_now", "format_elapsed"]
