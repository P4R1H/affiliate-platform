from __future__ import annotations
"""SQLAlchemy model for reports submitted by affiliates (their claims)."""
import enum
from typing import TYPE_CHECKING
from sqlalchemy import Integer, ForeignKey, DateTime, Enum, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column

if TYPE_CHECKING:  # pragma: no cover
    from .posts import Post
    from .reconciliation_logs import ReconciliationLog
from sqlalchemy.sql import func
from app.database import Base

class SubmissionMethod(str, enum.Enum):
    API = "API"
    DISCORD = "DISCORD"

class ReportStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"

class AffiliateReport(Base):
    __tablename__ = "affiliate_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id"), nullable=False)

    claimed_views: Mapped[int] = mapped_column(Integer, default=0)
    claimed_clicks: Mapped[int] = mapped_column(Integer, default=0)
    claimed_conversions: Mapped[int] = mapped_column(Integer, default=0)

    evidence_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Flags captured during submission validation (e.g., high_ctr, monotonicity_violation)
    suspicion_flags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    submission_method: Mapped[SubmissionMethod] = mapped_column(Enum(SubmissionMethod), nullable=False)
    status: Mapped[ReportStatus] = mapped_column(Enum(ReportStatus), default=ReportStatus.PENDING, index=True)

    submitted_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    post: Mapped["Post"] = relationship("Post", back_populates="affiliate_reports")
    reconciliation_log: Mapped[ReconciliationLog | None] = relationship("ReconciliationLog", back_populates="affiliate_report", uselist=False)
