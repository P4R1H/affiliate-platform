"""Data quality & anomaly detection for affiliate submissions.

Each rule returns either None (no issue) or a structured flag dict capturing:
  key: unique identifier for the rule
  value: measured ratio/delta/etc.
  threshold: configured threshold it exceeded (if applicable)
  severity: LOW|MEDIUM|HIGH (heuristic)
  message: human readable description

Public entrypoint: evaluate_submission(...)

Design principles:
- Pure functions (no side effects) except reading configuration.
- Centralizes heuristics so the endpoint stays lean.
- Returns a dict[str, dict] suitable for direct JSON storage in suspicion_flags.
"""
from __future__ import annotations
from typing import Any, Dict, Optional, List
from sqlalchemy.orm import Session
from app.config import DATA_QUALITY_SETTINGS
from app.models.db import AffiliateReport, Post

Severity = str  # alias for readability

# ----------------------------- helper utilities ----------------------------- #

def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _growth_pct(new: int, old: int) -> float:
    if old <= 0:
        return float('inf') if new > 0 else 0.0
    return (new - old) / old


def _severity_from_excess(excess_multiplier: float) -> Severity:
    # >3x threshold => HIGH, >1.5x => MEDIUM else LOW
    if excess_multiplier >= 3:
        return "HIGH"
    if excess_multiplier >= 1.5:
        return "MEDIUM"
    return "LOW"

# ----------------------------- rule implementations ----------------------------- #

def _rule_high_ctr(claimed_views: int, claimed_clicks: int) -> Optional[dict]:
    min_views = int(DATA_QUALITY_SETTINGS.get("min_views_for_ctr", 100))
    if claimed_views < min_views:
        return None
    ctr = _ratio(claimed_clicks, claimed_views)
    threshold = float(DATA_QUALITY_SETTINGS.get("max_ctr_pct", 0.35))
    if ctr > threshold:
        sev = _severity_from_excess(ctr / threshold)
        return {
            "key": "high_ctr",
            "value": round(ctr, 4),
            "threshold": threshold,
            "severity": sev,
            "message": f"CTR {ctr:.2%} exceeds {threshold:.0%} threshold",
        }
    return None

def _rule_high_cvr(claimed_clicks: int, claimed_conversions: int) -> Optional[dict]:
    min_clicks = int(DATA_QUALITY_SETTINGS.get("min_clicks_for_cvr", 20))
    if claimed_clicks < min_clicks:
        return None
    cvr = _ratio(claimed_conversions, claimed_clicks)
    threshold = float(DATA_QUALITY_SETTINGS.get("max_cvr_pct", 0.60))
    if cvr > threshold:
        sev = _severity_from_excess(cvr / threshold)
        return {
            "key": "high_cvr",
            "value": round(cvr, 4),
            "threshold": threshold,
            "severity": sev,
            "message": f"CVR {cvr:.2%} exceeds {threshold:.0%} threshold",
        }
    return None

def _rule_metric_order(claimed_views: int, claimed_clicks: int, claimed_conversions: int) -> Optional[dict]:
    if not (claimed_views >= claimed_clicks >= claimed_conversions):
        return {
            "key": "metric_order_violation",
            "severity": "MEDIUM",
            "message": "Expected views >= clicks >= conversions",
        }
    return None

def _rule_evidence_required(claimed_views: int, has_evidence: bool) -> Optional[dict]:
    threshold = int(DATA_QUALITY_SETTINGS.get("evidence_required_views", 50000))
    if claimed_views >= threshold and not has_evidence:
        return {
            "key": "missing_evidence",
            "severity": "MEDIUM",
            "message": f"Views {claimed_views} exceed {threshold} but no evidence provided",
        }
    return None

def _rule_non_monotonic(previous_report: Optional[AffiliateReport], claimed_views: int, claimed_clicks: int, claimed_conversions: int) -> List[dict]:
    if not previous_report:
        return []
    flags: List[dict] = []
    tol = float(DATA_QUALITY_SETTINGS.get("monotonic_tolerance", 0.01))
    def check(name: str, new: int, old: int):
        if old <= 0:
            return
        if new + int(old * tol) < old:  # allow small tolerance
            flags.append({
                "key": f"{name}_decrease",
                "severity": "LOW",
                "message": f"{name} decreased from {old} to {new}",
                "previous": old,
                "current": new,
            })
    check("views", claimed_views, previous_report.claimed_views)
    check("clicks", claimed_clicks, previous_report.claimed_clicks)
    check("conversions", claimed_conversions, previous_report.claimed_conversions)
    return flags

def _rule_spike(previous_report: Optional[AffiliateReport], claimed_views: int, claimed_clicks: int, claimed_conversions: int) -> List[dict]:
    if not previous_report:
        return []
    flags: List[dict] = []
    def maybe(name: str, new: int, old: int, cfg_key: str):
        growth = _growth_pct(new, old)
        threshold = float(DATA_QUALITY_SETTINGS.get(cfg_key, 5.0))
        if growth == float('inf'):
            return
        if growth > threshold:
            flags.append({
                "key": f"{name}_spike",
                "severity": "HIGH",
                "value": round(growth, 2),
                "threshold": threshold,
                "message": f"{name} grew {growth*100:.0f}% vs previous > {threshold*100:.0f}% threshold",
            })
    maybe("views", claimed_views, previous_report.claimed_views, "max_views_growth_pct")
    maybe("clicks", claimed_clicks, previous_report.claimed_clicks, "max_clicks_growth_pct")
    maybe("conversions", claimed_conversions, previous_report.claimed_conversions, "max_conversions_growth_pct")
    return flags

# ----------------------------- public entrypoint ----------------------------- #

def evaluate_submission(db: Session, *, post: Post | None, claimed_views: int, claimed_clicks: int, claimed_conversions: int, evidence_data: dict | None) -> Dict[str, dict]:
    """Evaluate a new submission and return suspicion flags.

    Args:
        db: Session (unused now but reserved for future historical aggregates)
        post: Existing post (None if brand new) to derive previous affiliate report
        claimed_*: New claimed metrics
        evidence_data: Provided evidence payload
    Returns:
        dict of flags keyed by rule key.
    """
    previous_report: Optional[AffiliateReport] = None
    if post and post.affiliate_reports:
        # choose latest by submitted_at or fallback id
        previous_report = max(post.affiliate_reports, key=lambda r: (getattr(r, "submitted_at", None) or 0, r.id))

    flags: Dict[str, dict] = {}
    # Simple single-value rules
    for rule in (
        lambda: _rule_high_ctr(claimed_views, claimed_clicks),
        lambda: _rule_high_cvr(claimed_clicks, claimed_conversions),
        lambda: _rule_metric_order(claimed_views, claimed_clicks, claimed_conversions),
        lambda: _rule_evidence_required(claimed_views, bool(evidence_data)),
    ):
        result = rule()
        if result:
            flags[result["key"]] = result

    # Multi-flag rules
    for r in _rule_non_monotonic(previous_report, claimed_views, claimed_clicks, claimed_conversions):
        flags[r["key"]] = r
    for r in _rule_spike(previous_report, claimed_views, claimed_clicks, claimed_conversions):
        flags[r["key"]] = r

    return flags

__all__ = ["evaluate_submission"]
