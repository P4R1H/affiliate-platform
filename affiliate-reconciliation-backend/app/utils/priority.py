"""Priority utilities centralizing mapping from trust bucket + flags -> queue priority label."""
from __future__ import annotations
from app.services.trust_scoring import bucket_for_priority

PRIORITY_MAP = {
    "critical": "high",
    "low_trust": "high",
    "normal": "normal",
    "high_trust": "low",
}

def compute_priority(trust_score: float, has_suspicion_flags: bool) -> str:
    """Compute queue priority based on trust score and suspicion flags."""
    bucket = bucket_for_priority(trust_score)
    label = PRIORITY_MAP.get(bucket, "normal")
    if has_suspicion_flags and label != "high":
        return "high"  # escalate
    return label

__all__ = ["compute_priority", "PRIORITY_MAP"]
