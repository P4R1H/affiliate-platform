"""Reconciliation job payload structure."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class ReconciliationJob:
    affiliate_report_id: int
    priority: str = "normal"
    scheduled_at: float | None = None  # epoch seconds (optional external usage)
    correlation_id: Optional[str] = None

    def key(self) -> str:  # can be used for idempotency if needed later
        return f"rec:{self.affiliate_report_id}"


__all__ = ["ReconciliationJob"]
