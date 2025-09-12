from __future__ import annotations
"""SQLAlchemy model for platform source-of-truth data per post."""
from typing import TYPE_CHECKING
from sqlalchemy import Integer, Numeric, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column

if TYPE_CHECKING:  # pragma: no cover
    from .posts import Post
    from .platforms import Platform
    from .reconciliation_logs import ReconciliationLog
from sqlalchemy.sql import func
from app.database import Base

class PlatformReport(Base):
    __tablename__ = "platform_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id"), nullable=False)
    platform_id: Mapped[int] = mapped_column(Integer, ForeignKey("platforms.id"), nullable=False)

    views: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)
    spend: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00)

    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fetched_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    post: Mapped["Post"] = relationship("Post", back_populates="platform_reports")
    platform: Mapped["Platform"] = relationship("Platform", back_populates="platform_reports")
    reconciliation_logs: Mapped[list["ReconciliationLog"]] = relationship("ReconciliationLog", back_populates="platform_report")

