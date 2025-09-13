"""Trust scoring logic (0-1 scale).

Takes current score and event type; returns new clamped score & delta.
"""
from __future__ import annotations

from typing import Tuple

from app.config import TRUST_SCORING
from app.models.db.enums import TrustEvent


def apply_trust_event(current: float, event: TrustEvent) -> Tuple[float, float]:
    """Apply a trust event to current score.

    Args:
        current: existing trust score (expected 0-1)
        event: TrustEvent
    Returns:
        (new_score, delta_applied)
    """
    events_cfg = TRUST_SCORING.get("events", {})  # type: ignore[assignment]
    # events_cfg may be Any; ensure dict-like before access
    if isinstance(events_cfg, dict):
        delta_raw = events_cfg.get(event.value, 0.0)
    else:  # defensive fallback
        delta_raw = 0.0
    delta = float(delta_raw)
    new_score = current + delta
    new_score = max(TRUST_SCORING["min_score"], min(new_score, TRUST_SCORING["max_score"]))  # type: ignore[index]
    # Adjust delta if clamped
    effective_delta = new_score - current
    return new_score, effective_delta


def bucket_for_priority(score: float) -> str:
    """Return qualitative bucket for downstream prioritisation.
    Possible buckets: high_trust, normal, low_trust, critical.
    """
    if score >= TRUST_SCORING["reduced_frequency_threshold"]:  # type: ignore[index]
        return "high_trust"
    if score >= TRUST_SCORING["increased_monitoring_threshold"]:  # type: ignore[index]
        return "normal"
    if score >= TRUST_SCORING["manual_review_threshold"]:  # type: ignore[index]
        return "low_trust"
    return "critical"


__all__ = ["apply_trust_event", "bucket_for_priority"]
