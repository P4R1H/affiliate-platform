from __future__ import annotations
"""SQLAlchemy model for reconciliation logs."""
import enum
from typing import TYPE_CHECKING
from sqlalchemy import Integer, Text, DateTime, ForeignKey, Enum, Numeric
from sqlalchemy.orm import relationship, Mapped, mapped_column

if TYPE_CHECKING:  # pragma: no cover
    from .affiliate_reports import AffiliateReport
    from .platform_reports import PlatformReport
    from .alerts import Alert
from sqlalchemy.sql import func
from app.database import Base

class DiscrepancyLevel(str, enum.Enum):
    LOW = "LOW"        # < 5% difference
    MEDIUM = "MEDIUM"  # 5-20% difference  
    HIGH = "HIGH"      # > 20% difference

class ReconciliationStatus(str, enum.Enum):
    MATCHED = "MATCHED"
    DISCREPANCY = "DISCREPANCY" 
    MISSING_PLATFORM_DATA = "MISSING_PLATFORM_DATA"
    AFFILIATE_OVERCLAIMED = "AFFILIATE_OVERCLAIMED"  # A >> B case

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

    affiliate_report: Mapped["AffiliateReport"] = relationship("AffiliateReport", back_populates="reconciliation_log")
    platform_report: Mapped[PlatformReport | None] = relationship("PlatformReport", back_populates="reconciliation_logs")
    alert: Mapped[Alert | None] = relationship("Alert", back_populates="reconciliation_log", uselist=False)

