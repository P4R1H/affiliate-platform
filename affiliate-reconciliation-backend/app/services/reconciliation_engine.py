"""Reconciliation engine orchestrator.

Single public function `run_reconciliation(session, affiliate_report_id)` that:
1. Loads AffiliateReport (+ Post, Affiliate, Platform as needed).
2. Ensures a ReconciliationLog row exists (creates placeholder if missing).
3. Fetches platform metrics via PlatformFetcher.
4. Classifies discrepancies (growth adjusted) via classify().
5. Applies trust scoring if applicable.
6. Persists / updates PlatformReport (optional for partial data).
7. Updates ReconciliationLog fields (attempt tracking, diffs, status, retry schedule).
8. Returns structured dict summary for API / job usage.

Retry scheduling policy (MVP):
* MISSING_PLATFORM_DATA: schedule next attempt if attempts < max and within window.
* INCOMPLETE_PLATFORM_DATA: allow one additional attempt (if confidence_ratio < 1 and attempts == 1).
* Otherwise no retry (scheduled_retry_at None).

Alerting hook placeholder (will integrate when alerting service implemented).
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.db.affiliate_reports import AffiliateReport
from app.models.db.reconciliation_logs import ReconciliationLog
from app.models.db.platform_reports import PlatformReport
from app.models.db.users import User
from app.models.db.posts import Post
from app.models.db.platforms import Platform
from app.models.db.enums import ReconciliationStatus, TrustEvent

from app.services.platform_fetcher import PlatformFetcher
from app.services.discrepancy_classifier import classify
from app.services.trust_scoring import apply_trust_event
from app.services.alerting import maybe_create_alert

from app.config import RETRY_POLICY
from app.utils import get_logger

logger = get_logger(__name__)


def _ensure_log(session: Session, report: AffiliateReport) -> ReconciliationLog:
    # Robust single-row get/create with retry for rare race conditions
    if report.reconciliation_log:
        return report.reconciliation_log
    # Attempt insert; on integrity error (unique constraint) load existing
    from sqlalchemy.exc import IntegrityError
    try:
        log = ReconciliationLog(
            affiliate_report_id=report.id,
            status=ReconciliationStatus.MISSING_PLATFORM_DATA,  # placeholder initial
            attempt_count=0,
        )
        session.add(log)
        session.flush()
        return log
    except IntegrityError:
        session.rollback()
        existing = session.query(ReconciliationLog).filter_by(affiliate_report_id=report.id).one()
        return existing


def _schedule_retry(status: ReconciliationStatus, attempt_count: int, submitted_at: datetime, now: datetime) -> datetime | None:
    if status == ReconciliationStatus.MISSING_PLATFORM_DATA:
        cfg = RETRY_POLICY.get("missing_platform_data", {})
        max_attempts = int(cfg.get("max_attempts", 5))
        window_hours = float(cfg.get("window_hours", 24))
        initial_delay_minutes = int(cfg.get("initial_delay_minutes", 30))
        if attempt_count >= max_attempts:
            return None
        if (now - submitted_at).total_seconds() / 3600.0 > window_hours:
            return None
        # Simple linear backoff: initial + attempt_count * initial
        delay_minutes = initial_delay_minutes * max(1, attempt_count)
        return now + timedelta(minutes=delay_minutes)
    if status == ReconciliationStatus.INCOMPLETE_PLATFORM_DATA:
        cfg_incomplete = RETRY_POLICY.get("incomplete_platform_data", {})
        max_additional = int(cfg_incomplete.get("max_additional_attempts", 1))
        # attempt_count is total attempts so far *after* increment; allow if <= 1 + max_additional
        if attempt_count <= 1 + max_additional:
            return now + timedelta(minutes=15)
        return None
    return None


def run_reconciliation(session: Session, affiliate_report_id: int) -> Dict[str, Any]:
    """Run reconciliation for an affiliate report.

    Fetches platform data, classifies discrepancies, applies trust scoring,
    and updates reconciliation log with results.
    """
    now = datetime.now(timezone.utc)
    report: AffiliateReport | None = session.query(AffiliateReport).filter(AffiliateReport.id == affiliate_report_id).one_or_none()
    if report is None:
        raise ValueError(f"AffiliateReport {affiliate_report_id} not found")

    post: Post = report.post  # lazy relationship
    user: User = post.user
    platform: Platform = post.platform

    log = _ensure_log(session, report)
    # Compute elapsed hours since submission
    # SQLAlchemy attribute typing may not reflect runtime datetime object; cast defensively
    submitted_at_raw = report.submitted_at if isinstance(report.submitted_at, datetime) else now
    # Normalize naive datetimes to UTC to avoid subtraction errors
    if submitted_at_raw.tzinfo is None:  # type: ignore[union-attr]
        submitted_at_dt = submitted_at_raw.replace(tzinfo=timezone.utc)  # type: ignore[assignment]
    else:
        submitted_at_dt = submitted_at_raw  # type: ignore[assignment]
    elapsed_hours = max(0.0, (now - submitted_at_dt).total_seconds() / 3600.0)

    fetcher = PlatformFetcher()
    outcome = fetcher.fetch(platform.name, post.url)

    platform_views = outcome.platform_metrics.get("views") if outcome.platform_metrics else None
    platform_clicks = outcome.platform_metrics.get("clicks") if outcome.platform_metrics else None
    platform_conversions = outcome.platform_metrics.get("conversions") if outcome.platform_metrics else None

    classification = classify(
        claimed_views=report.claimed_views,
        claimed_clicks=report.claimed_clicks,
        claimed_conversions=report.claimed_conversions,
        platform_views=platform_views,
        platform_clicks=platform_clicks,
        platform_conversions=platform_conversions,
        elapsed_hours=elapsed_hours,
        partial_missing=outcome.partial_missing,
    )

    # Trust scoring
    trust_delta = 0.0
    if classification.trust_event:
        current_trust = user.trust_score or 0.5  # Default trust score if None
        new_trust, trust_delta = apply_trust_event(float(current_trust), classification.trust_event)
        user.trust_score = new_trust
        user.last_trust_update = now  # type: ignore[assignment]
        if classification.trust_event == TrustEvent.PERFECT_MATCH:
            user.accurate_submissions += 1

    # Persist / update platform report if we have at least one metric (success path)
    platform_report_obj: PlatformReport | None = None
    if outcome.platform_metrics and any(v is not None for v in outcome.platform_metrics.values()):
        # For MVP: create a new PlatformReport per attempt (could also upsert latest)
        platform_report_obj = PlatformReport(
            post_id=post.id,
            platform_id=platform.id,
            views=platform_views or 0,
            clicks=platform_clicks or 0,
            conversions=platform_conversions or 0,
            raw_data=outcome.platform_metrics,
        )
        session.add(platform_report_obj)
        session.flush()
        log.platform_report_id = platform_report_obj.id

    # Update reconciliation log
    log.attempt_count = (log.attempt_count or 0) + 1
    log.last_attempt_at = now  # type: ignore[assignment]
    log.elapsed_hours = elapsed_hours
    log.status = classification.status
    log.views_discrepancy = classification.views_discrepancy
    log.clicks_discrepancy = classification.clicks_discrepancy
    log.conversions_discrepancy = classification.conversions_discrepancy
    log.views_diff_pct = classification.views_diff_pct
    log.clicks_diff_pct = classification.clicks_diff_pct
    log.conversions_diff_pct = classification.conversions_diff_pct
    log.max_discrepancy_pct = classification.max_discrepancy_pct
    log.discrepancy_level = classification.discrepancy_level  # type: ignore[assignment]
    log.missing_fields = {"fields": classification.missing_fields} if classification.missing_fields else None
    log.confidence_ratio = classification.confidence_ratio
    log.trust_delta = trust_delta if trust_delta != 0 else None
    log.error_code = outcome.error_code
    log.error_message = outcome.error_message
    log.rate_limited = outcome.rate_limited

    # Retry scheduling
    retry_time = _schedule_retry(classification.status, log.attempt_count, submitted_at_dt, now)
    log.scheduled_retry_at = retry_time  # type: ignore[assignment]

    # Finalization of post if terminal outcome
    terminal_statuses = {
        ReconciliationStatus.MATCHED,
        ReconciliationStatus.AFFILIATE_OVERCLAIMED,
        ReconciliationStatus.DISCREPANCY_HIGH,
    }
    if classification.status in terminal_statuses and retry_time is None:
        post.is_reconciled = True

    # Alert creation (before commit so alert persists atomically with log changes)
    retry_scheduled_flag = retry_time is not None
    maybe_create_alert(session, log, user=user, post=post, retry_scheduled=retry_scheduled_flag)

    from sqlalchemy.orm.exc import StaleDataError
    try:
        session.commit()
    except StaleDataError as sde:  # rare race condition on SQLite rowcount heuristics
        logger.warning(
            "StaleDataError on commit – retrying once",
            report_id=report.id,
            error=str(sde),
        )
        session.rollback()
        # Merge current in-memory state and retry
        try:
            session.merge(log)
            session.commit()
        except StaleDataError:
            logger.error("Second StaleDataError on commit – aborting", report_id=report.id)
            raise

    return {
        "affiliate_report_id": report.id,
        "status": classification.status.value,
        "attempt_count": log.attempt_count,
        "scheduled_retry_at": retry_time.isoformat() if retry_time else None,
        "trust_delta": trust_delta if trust_delta != 0 else 0.0,
        "new_trust_score": float(user.trust_score or 0.5),
        "discrepancy_level": classification.discrepancy_level,
        "max_discrepancy_pct": float(classification.max_discrepancy_pct) if classification.max_discrepancy_pct is not None else None,
        "rate_limited": outcome.rate_limited,
        "error_code": outcome.error_code,
        "missing_fields": classification.missing_fields,
    }


__all__ = ["run_reconciliation"]
