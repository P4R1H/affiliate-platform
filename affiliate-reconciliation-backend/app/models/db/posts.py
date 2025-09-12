from __future__ import annotations
"""SQLAlchemy model for individual posts submitted by affiliates."""
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, ForeignKey, DateTime, Boolean, UniqueConstraint, Column
from sqlalchemy.orm import relationship, Mapped, mapped_column

if TYPE_CHECKING:  # pragma: no cover
    from .campaigns import Campaign
    from .affiliates import Affiliate
    from .platforms import Platform
    from .affiliate_reports import AffiliateReport
    from .platform_reports import PlatformReport
from sqlalchemy.sql import func
from app.database import Base

class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id"), nullable=False)
    affiliate_id: Mapped[int] = mapped_column(Integer, ForeignKey("affiliates.id"), nullable=False)
    platform_id: Mapped[int] = mapped_column(Integer, ForeignKey("platforms.id"), nullable=False)

    url: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    is_reconciled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="posts")
    affiliate: Mapped["Affiliate"] = relationship("Affiliate", back_populates="posts")
    platform: Mapped["Platform"] = relationship("Platform", back_populates="posts")
    affiliate_reports: Mapped[list["AffiliateReport"]] = relationship("AffiliateReport", back_populates="post")
    platform_reports: Mapped[list["PlatformReport"]] = relationship("PlatformReport", back_populates="post")

    # Constraints - Prevent duplicate posts from same affiliate
    __table_args__ = (
        UniqueConstraint('campaign_id', 'platform_id', 'url', 'affiliate_id', 
                        name='unique_affiliate_post_per_campaign'),
    )

