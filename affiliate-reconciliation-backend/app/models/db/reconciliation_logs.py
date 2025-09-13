from __future__ import annotations
"""SQLAlchemy model for reconciliation logs."""
import enum
from typing import TYPE_CHECKING
from sqlalchemy import Integer, Text, DateTime, ForeignKey, Enum, Numeric, Boolean, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column

if TYPE_CHECKING:  # pragma: no cover
    from .affiliate_reports import AffiliateReport
    from .platform_reports import PlatformReport
    from .alerts import Alert
from sqlalchemy.sql import func
from app.database import Base

class DiscrepancyLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

# Use centralized ReconciliationStatus enum from enums module (includes LOW/MEDIUM/HIGH granularity etc.)
from .enums import ReconciliationStatus  # noqa: E402

class ReconciliationLog(Base):
    __tablename__ = "reconciliation_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    affiliate_report_id: Mapped[int] = mapped_column(Integer, ForeignKey("affiliate_reports.id"), nullable=False, unique=True)
    platform_report_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("platform_reports.id"), nullable=True)

    status: Mapped[ReconciliationStatus] = mapped_column(Enum(ReconciliationStatus), nullable=False, index=True)
    discrepancy_level: Mapped[DiscrepancyLevel | None] = mapped_column(Enum(DiscrepancyLevel), nullable=True, index=True)

    views_discrepancy: Mapped[int] = mapped_column(Integer, default=0)
    clicks_discrepancy: Mapped[int] = mapped_column(Integer, default=0)
    conversions_discrepancy: Mapped[int] = mapped_column(Integer, default=0)

    views_diff_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    clicks_diff_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    conversions_diff_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Retry / attempt tracking (single-row strategy; values updated on each attempt)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_retry_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Aggregated metrics & meta
    max_discrepancy_pct: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    confidence_ratio: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    missing_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rate_limited: Mapped[bool] = mapped_column(Boolean, default=False)
    elapsed_hours: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    trust_delta: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    affiliate_report: Mapped["AffiliateReport"] = relationship("AffiliateReport", back_populates="reconciliation_log")
    platform_report: Mapped[PlatformReport | None] = relationship("PlatformReport", back_populates="reconciliation_log")
    alert: Mapped[Alert | None] = relationship("Alert", back_populates="reconciliation_log", uselist=False)

