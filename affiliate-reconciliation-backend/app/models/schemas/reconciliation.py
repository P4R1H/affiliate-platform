"""
Pydantic schemas for reconciliation operations.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from .base import UnifiedMetrics

class ReconciliationTrigger(BaseModel):
    """
    Schema for triggering reconciliation jobs (if manual trigger needed).
    """
    post_id: Optional[int] = Field(None, description="Specific post ID to reconcile, or None for all pending")
    force_reprocess: bool = Field(False, description="Reprocess even if already reconciled")

class DiscrepancyDetail(BaseModel):
    """Granular discrepancy computation for a metric."""
    metric: str = Field(description="views|clicks|conversions")
    claimed: int
    observed: Optional[int] = Field(None, description="Observed platform value (None if missing/incomplete platform data)")
    absolute_diff: int
    pct_diff: Optional[float] = Field(None, description="Percentage difference (claimed - observed)/observed if observed>0")

class TrustScoreChange(BaseModel):
    """Represents a trust score adjustment during reconciliation."""
    event: Optional[str] = Field(None, description="TrustEvent value applied; None if no change")
    previous: float
    new: float
    delta: float

class AlertPayload(BaseModel):
    """Lightweight embedded alert summary when reconciliation triggered an alert."""
    id: int
    alert_type: str
    severity: str
    category: Optional[str]
    title: str
    created_at: datetime

class ReconciliationJobPayload(BaseModel):
    """Metadata about the reconciliation job attempt for observability."""
    attempt_count: int = Field(description="Total attempts so far (including this one)")
    max_attempts: Optional[int] = Field(None, description="Configured max attempts if available")
    next_retry_at: Optional[datetime] = Field(None, description="If scheduled for retry, when the next attempt will occur")
    queue_priority: Optional[str] = Field(None, description="Priority label used when enqueuing")

class ReconciliationResult(BaseModel):
    """Extended reconciliation result including discrepancy breakdown, trust change and any alert metadata.

    Backwards compatibility: legacy top-level *_discrepancy and *_diff_pct fields are retained for existing clients.
    New clients should prefer `discrepancies` list.
    """
    id: int
    affiliate_report_id: int
    platform_report_id: Optional[int]
    status: str = Field(description="One of MATCHED, DISCREPANCY_LOW, DISCREPANCY_MEDIUM, DISCREPANCY_HIGH, AFFILIATE_OVERCLAIMED, MISSING_PLATFORM_DATA, INCOMPLETE_PLATFORM_DATA, UNVERIFIABLE, SKIPPED_SUSPENDED")
    discrepancy_level: Optional[str] = Field(description="LOW, MEDIUM, HIGH, CRITICAL (CRITICAL only for severe overclaim)")

    # Legacy aggregated discrepancy fields (kept for compatibility)
    views_discrepancy: int
    clicks_discrepancy: int
    conversions_discrepancy: int
    views_diff_pct: Optional[float]
    clicks_diff_pct: Optional[float]
    conversions_diff_pct: Optional[float]

    # New richer fields
    discrepancies: List[DiscrepancyDetail] = Field(default_factory=list)
    max_discrepancy_pct: Optional[float] = Field(None, description="Max absolute percentage diff across metrics")
    trust_change: Optional[TrustScoreChange] = None
    alert: Optional[AlertPayload] = None
    job: Optional[ReconciliationJobPayload] = None
    meta: Dict[str, Any] = Field(default_factory=dict, description="Additional reconciliation metadata")

    notes: Optional[str]
    processed_at: datetime

    affiliate_metrics: UnifiedMetrics
    platform_metrics: Optional[UnifiedMetrics]

    class Config:
        from_attributes = True
