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
    ADMIN = "ADMIN"
