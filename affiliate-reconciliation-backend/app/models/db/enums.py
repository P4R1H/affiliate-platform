"""Central Enum definitions for core domain states.

These replace scattered string literals to ensure consistency across
DB models, schemas, and business logic while staying minimal per brief.
"""
from __future__ import annotations
import enum


class CampaignStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class UserRole(str, enum.Enum):
    AFFILIATE = "AFFILIATE"
    CLIENT = "CLIENT"
    ADMIN = "ADMIN"

# ------------------ Reconciliation / Discrepancy Enums ------------------ #

class ReconciliationStatus(str, enum.Enum):
    MATCHED = "MATCHED"
    DISCREPANCY_LOW = "DISCREPANCY_LOW"
    DISCREPANCY_MEDIUM = "DISCREPANCY_MEDIUM"
    DISCREPANCY_HIGH = "DISCREPANCY_HIGH"
    AFFILIATE_OVERCLAIMED = "AFFILIATE_OVERCLAIMED"
    MISSING_PLATFORM_DATA = "MISSING_PLATFORM_DATA"
    INCOMPLETE_PLATFORM_DATA = "INCOMPLETE_PLATFORM_DATA"
    UNVERIFIABLE = "UNVERIFIABLE"
    SKIPPED_SUSPENDED = "SKIPPED_SUSPENDED"

class AlertSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class AlertCategory(str, enum.Enum):
    DATA_QUALITY = "DATA_QUALITY"
    FRAUD = "FRAUD"
    SYSTEM_HEALTH = "SYSTEM_HEALTH"

class TrustEvent(str, enum.Enum):
    PERFECT_MATCH = "perfect_match"
    MINOR_DISCREPANCY = "minor_discrepancy"
    MEDIUM_DISCREPANCY = "medium_discrepancy"
    HIGH_DISCREPANCY = "high_discrepancy"
    OVERCLAIM = "overclaim"
    IMPOSSIBLE_SUBMISSION = "impossible_submission"
    MANUAL_ADJUST = "manual_adjust"

__all__ = [
    "CampaignStatus",
    "UserRole",
    "ReconciliationStatus",
    "AlertSeverity",
    "AlertCategory",
    "TrustEvent",
]
