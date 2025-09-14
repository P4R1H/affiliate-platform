"""Alert creation & escalation logic.

Rules (MVP):
1. AFFILIATE_OVERCLAIMED -> AlertType.HIGH_DISCREPANCY, category=FRAUD, severity HIGH or CRITICAL if discrepancy_level == CRITICAL.
2. DISCREPANCY_HIGH -> AlertType.HIGH_DISCREPANCY, category=DATA_QUALITY, severity HIGH; escalate to CRITICAL if similar high discrepancy alert for same affiliate & platform within repeat window.
3. MISSING_PLATFORM_DATA terminal (no retry scheduled) -> AlertType.MISSING_DATA, category=SYSTEM_HEALTH, severity MEDIUM.

Idempotency: only one alert per reconciliation_log. Additional escalation logic may update existing alert in future; for MVP we create once.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.db.alerts import Alert, AlertType, AlertStatus
from app.models.db.reconciliation_logs import ReconciliationLog, DiscrepancyLevel
from app.models.db.users import User
from app.models.db.posts import Post
from app.models.db.enums import (
    ReconciliationStatus,
    AlertCategory,
    AlertSeverity,
)
from app.config import ALERTING_SETTINGS
from app.utils import get_logger

logger = get_logger(__name__)


def _repeat_high_discrepancy(session: Session, user_id: int, platform_id: int, now: datetime) -> bool:
    window_hours = float(ALERTING_SETTINGS.get("repeat_overclaim_window_hours", 6))
    window_start = now - timedelta(hours=window_hours)
    count = (
        session.query(Alert)
        .filter(
            Alert.user_id == user_id,
            Alert.platform_id == platform_id,
            Alert.alert_type == AlertType.HIGH_DISCREPANCY,
            Alert.created_at >= window_start,
        )
        .count()
    )
    return count > 0


def maybe_create_alert(
    session: Session,
    log: ReconciliationLog,
    *,
    user: User,
    post: Post,
    retry_scheduled: bool,
) -> Optional[Alert]:
    """Create an alert if reconciliation status warrants it.

    Only creates one alert per reconciliation log.
    """
    # Do not create if already present
    if log.alert is not None:
        return None

    now = datetime.now(timezone.utc)
    status = log.status

    # Rule 1: Affiliate overclaimed
    if status == ReconciliationStatus.AFFILIATE_OVERCLAIMED:
        severity = AlertSeverity.CRITICAL if log.discrepancy_level == DiscrepancyLevel.CRITICAL else AlertSeverity.HIGH
        alert = Alert(
            reconciliation_log_id=log.id,
            user_id=user.id,
            platform_id=post.platform_id,
            alert_type=AlertType.HIGH_DISCREPANCY,
            title="Affiliate overclaim detected",
            message="Affiliate claimed metrics significantly exceed platform source-of-truth.",
            threshold_breached={"discrepancy_level": log.discrepancy_level, "max_discrepancy_pct": float(log.max_discrepancy_pct) if log.max_discrepancy_pct is not None else None},
            category=AlertCategory.FRAUD,
            severity=severity,
        )
        session.add(alert)
        logger.info("Created overclaim alert", log_id=log.id, severity=severity.value)
        return alert

    # Rule 2: High discrepancy (non-overclaim)
    if status == ReconciliationStatus.DISCREPANCY_HIGH:
        severity = AlertSeverity.HIGH
        if _repeat_high_discrepancy(session, user.id, post.platform_id, now):
            severity = AlertSeverity.CRITICAL
        alert = Alert(
            reconciliation_log_id=log.id,
            user_id=user.id,
            platform_id=post.platform_id,
            alert_type=AlertType.HIGH_DISCREPANCY,
            title="High discrepancy detected",
            message="Large variance between claimed and platform metrics.",
            threshold_breached={"discrepancy_level": log.discrepancy_level, "max_discrepancy_pct": float(log.max_discrepancy_pct) if log.max_discrepancy_pct is not None else None},
            category=AlertCategory.DATA_QUALITY,
            severity=severity,
        )
        session.add(alert)
        logger.info("Created high discrepancy alert", log_id=log.id, severity=severity.value)
        return alert

    # Rule 3: Missing platform data terminal (no retry scheduled)
    if status == ReconciliationStatus.MISSING_PLATFORM_DATA and not retry_scheduled:
        alert = Alert(
            reconciliation_log_id=log.id,
            user_id=user.id,
            platform_id=post.platform_id,
            alert_type=AlertType.MISSING_DATA,
            title="Platform data missing",
            message="Platform data unavailable after retries; manual investigation required.",
            threshold_breached={"attempts": log.attempt_count},
            category=AlertCategory.SYSTEM_HEALTH,
            severity=AlertSeverity.MEDIUM,
        )
        session.add(alert)
        logger.info("Created missing data alert", log_id=log.id)
        return alert

    return None


__all__ = ["maybe_create_alert"]
