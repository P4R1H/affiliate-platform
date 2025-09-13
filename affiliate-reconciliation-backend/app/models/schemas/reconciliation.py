"""
Pydantic schemas for reconciliation operations.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from .base import UnifiedMetrics

class ReconciliationTrigger(BaseModel):
    """
    Schema for triggering reconciliation jobs (if manual trigger needed).
    """
    post_id: Optional[int] = Field(None, description="Specific post ID to reconcile, or None for all pending")
    force_reprocess: bool = Field(False, description="Reprocess even if already reconciled")

class ReconciliationResult(BaseModel):
    """
    Schema for reconciliation results and status.
    """
    id: int
    affiliate_report_id: int
    platform_report_id: Optional[int]
    status: str = Field(description="One of MATCHED, DISCREPANCY_LOW, DISCREPANCY_MEDIUM, DISCREPANCY_HIGH, AFFILIATE_OVERCLAIMED, MISSING_PLATFORM_DATA, INCOMPLETE_PLATFORM_DATA, UNVERIFIABLE, SKIPPED_SUSPENDED")
    discrepancy_level: Optional[str] = Field(description="LOW, MEDIUM, HIGH, CRITICAL (CRITICAL only for severe overclaim)")
    
    # Discrepancy details
    views_discrepancy: int
    clicks_discrepancy: int
    conversions_discrepancy: int
    views_diff_pct: Optional[float]
    clicks_diff_pct: Optional[float]
    conversions_diff_pct: Optional[float]
    
    notes: Optional[str]
    processed_at: datetime
    
    # Included data for context
    affiliate_metrics: UnifiedMetrics
    platform_metrics: Optional[UnifiedMetrics]
    
    class Config:
        from_attributes = True
