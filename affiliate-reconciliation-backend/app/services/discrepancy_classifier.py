"""Discrepancy classification logic.

Inputs are raw claimed metrics & platform metrics; we apply configurable
growth allowance + tolerance tiers to derive a ReconciliationStatus and
associated TrustEvent.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.config import RECONCILIATION_SETTINGS
from app.models.db.enums import (
    ReconciliationStatus,
    TrustEvent,
)
from app.utils.metrics import pct_diff, apply_growth_allowance


@dataclass
class ClassificationResult:
    status: ReconciliationStatus
    trust_event: Optional[TrustEvent]
    views_discrepancy: int
    clicks_discrepancy: int
    conversions_discrepancy: int
    views_diff_pct: Optional[float]
    clicks_diff_pct: Optional[float]
    conversions_diff_pct: Optional[float]
    max_discrepancy_pct: Optional[float]
    discrepancy_level: Optional[str]
    missing_fields: list[str]
    confidence_ratio: Optional[float]


def classify(
    claimed_views: int,
    claimed_clicks: int,
    claimed_conversions: int,
    platform_views: Optional[int],
    platform_clicks: Optional[int],
    platform_conversions: Optional[int],
    *,
    elapsed_hours: float,
    partial_missing: list[str] | None = None,
) -> ClassificationResult:
    """Core classification algorithm.

    If all platform metrics are None -> MISSING_PLATFORM_DATA.
    If some are missing -> INCOMPLETE_PLATFORM_DATA (still compare provided ones).
    """
    missing = partial_missing[:] if partial_missing else []
    # Early fully-missing case (all metrics absent)
    if platform_views is None and platform_clicks is None and platform_conversions is None:
        return ClassificationResult(
            status=ReconciliationStatus.MISSING_PLATFORM_DATA,
            trust_event=None,
            views_discrepancy=0,
            clicks_discrepancy=0,
            conversions_discrepancy=0,
            views_diff_pct=None,
            clicks_diff_pct=None,
            conversions_diff_pct=None,
            max_discrepancy_pct=None,
            discrepancy_level=None,
            missing_fields=["views", "clicks", "conversions"],
            confidence_ratio=0.0,
        )

    # Determine partial status
    provided_metrics = 0
    expected_metrics = 3
    if platform_views is not None:
        provided_metrics += 1
    else:
        missing.append("views")
    if platform_clicks is not None:
        provided_metrics += 1
    else:
        missing.append("clicks")
    if platform_conversions is not None:
        provided_metrics += 1
    else:
        missing.append("conversions")

    confidence_ratio = provided_metrics / expected_metrics

    # Growth allowance adjusted platform values where present
    growth_per_hour_cfg = RECONCILIATION_SETTINGS.get("growth_per_hour_pct", 0.0)
    cap_hours_cfg = RECONCILIATION_SETTINGS.get("growth_cap_hours", 0)
    growth_per_hour = float(growth_per_hour_cfg) if isinstance(growth_per_hour_cfg, (int, float)) else 0.0
    cap_hours = int(cap_hours_cfg) if isinstance(cap_hours_cfg, (int, float)) else 0

    adj_views = apply_growth_allowance(platform_views, elapsed_hours, growth_per_hour, cap_hours) if platform_views is not None else None
    adj_clicks = apply_growth_allowance(platform_clicks, elapsed_hours, growth_per_hour, cap_hours) if platform_clicks is not None else None
    adj_conversions = apply_growth_allowance(platform_conversions, elapsed_hours, growth_per_hour, cap_hours) if platform_conversions is not None else None

    # Raw discrepancies (claimed - adjusted platform)
    views_discrepancy = claimed_views - (adj_views or 0)
    clicks_discrepancy = claimed_clicks - (adj_clicks or 0)
    conversions_discrepancy = claimed_conversions - (adj_conversions or 0)

    views_diff_pct = pct_diff(claimed_views, adj_views) if adj_views is not None else None
    clicks_diff_pct = pct_diff(claimed_clicks, adj_clicks) if adj_clicks is not None else None
    conversions_diff_pct = pct_diff(claimed_conversions, adj_conversions) if adj_conversions is not None else None

    diffs = [d for d in [views_diff_pct, clicks_diff_pct, conversions_diff_pct] if d is not None]
    max_diff = max(diffs) if diffs else None

    # Determine status
    if provided_metrics == 0:
        status = ReconciliationStatus.MISSING_PLATFORM_DATA
        trust_event = None
        discrepancy_level = None
    elif provided_metrics < expected_metrics:
        # partial data – we still evaluate discrepancies for available metrics
        status = ReconciliationStatus.INCOMPLETE_PLATFORM_DATA
        trust_event = None
        discrepancy_level = None
    else:
        # Full data path
        if max_diff is None:
            status = ReconciliationStatus.MATCHED
            trust_event = TrustEvent.PERFECT_MATCH
            discrepancy_level = None
        else:
            raw_base_tol = RECONCILIATION_SETTINGS.get("base_tolerance_pct", 0.05)
            base_tol = float(raw_base_tol) if isinstance(raw_base_tol, (int, float)) else 0.05
            tiers_cfg_any = RECONCILIATION_SETTINGS.get("discrepancy_tiers", {})
            tiers_cfg = tiers_cfg_any if isinstance(tiers_cfg_any, dict) else {}
            raw_low = tiers_cfg.get("low_max", 0.10)
            raw_med = tiers_cfg.get("medium_max", 0.20)
            low_max = float(raw_low) if isinstance(raw_low, (int, float)) else 0.10
            medium_max = float(raw_med) if isinstance(raw_med, (int, float)) else 0.20
            raw_over = RECONCILIATION_SETTINGS.get("overclaim_threshold_pct", 0.20)
            raw_crit = RECONCILIATION_SETTINGS.get("overclaim_critical_pct", 0.50)
            overclaim_threshold = float(raw_over) if isinstance(raw_over, (int, float)) else 0.20
            overclaim_critical = float(raw_crit) if isinstance(raw_crit, (int, float)) else 0.50

            # Overclaim detection (only if affiliate above adjusted platform for at least one metric significantly)
            overclaim_condition = (
                (views_discrepancy > 0 and views_diff_pct is not None and views_diff_pct >= overclaim_threshold) or
                (clicks_discrepancy > 0 and clicks_diff_pct is not None and clicks_diff_pct >= overclaim_threshold) or
                (conversions_discrepancy > 0 and conversions_diff_pct is not None and conversions_diff_pct >= overclaim_threshold)
            )
            critical_condition = (
                (views_discrepancy > 0 and views_diff_pct is not None and views_diff_pct >= overclaim_critical) or
                (clicks_discrepancy > 0 and clicks_diff_pct is not None and clicks_diff_pct >= overclaim_critical) or
                (conversions_discrepancy > 0 and conversions_diff_pct is not None and conversions_diff_pct >= overclaim_critical)
            )

            if overclaim_condition:
                status = ReconciliationStatus.AFFILIATE_OVERCLAIMED
                trust_event = TrustEvent.OVERCLAIM
                discrepancy_level = "CRITICAL" if critical_condition else "HIGH"
            elif max_diff <= base_tol:
                status = ReconciliationStatus.MATCHED
                trust_event = TrustEvent.PERFECT_MATCH
                discrepancy_level = None
            else:
                if max_diff <= low_max:
                    status = ReconciliationStatus.DISCREPANCY_LOW
                    trust_event = TrustEvent.MINOR_DISCREPANCY
                    discrepancy_level = "LOW"
                elif max_diff <= medium_max:
                    status = ReconciliationStatus.DISCREPANCY_MEDIUM
                    trust_event = TrustEvent.MEDIUM_DISCREPANCY
                    discrepancy_level = "MEDIUM"
                else:
                    status = ReconciliationStatus.DISCREPANCY_HIGH
                    trust_event = TrustEvent.HIGH_DISCREPANCY
                    discrepancy_level = "HIGH"

    return ClassificationResult(
        status=status,
        trust_event=trust_event,
        views_discrepancy=views_discrepancy,
        clicks_discrepancy=clicks_discrepancy,
        conversions_discrepancy=conversions_discrepancy,
        views_diff_pct=views_diff_pct,
        clicks_diff_pct=clicks_diff_pct,
        conversions_diff_pct=conversions_diff_pct,
        max_discrepancy_pct=max_diff,
        discrepancy_level=discrepancy_level,
        missing_fields=missing,
        confidence_ratio=confidence_ratio,
    )


__all__ = ["ClassificationResult", "classify"]
