from __future__ import annotations
"""SQLAlchemy model for advertising platforms (e.g., Reddit, Meta, Instagram)."""
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, DateTime, Table, ForeignKey, Boolean, JSON, Column
from sqlalchemy.orm import relationship, Mapped, mapped_column

if TYPE_CHECKING:  # pragma: no cover
    from .campaigns import Campaign
    from .posts import Post
    from .platform_reports import PlatformReport
from sqlalchemy.sql import func
from app.database import Base

# Association Table for Many-to-Many: Campaigns <-> Platforms
campaign_platform_association = Table(
    'campaign_platform_association', 
    Base.metadata,
    Column('campaign_id', Integer, ForeignKey('campaigns.id'), primary_key=True),
    Column('platform_id', Integer, ForeignKey('platforms.id'), primary_key=True)
)

class Platform(Base):
    __tablename__ = "platforms"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    api_base_url: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    api_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    campaigns: Mapped[list["Campaign"]] = relationship(
        "Campaign", secondary=campaign_platform_association, back_populates="platforms"
    )
    posts: Mapped[list["Post"]] = relationship("Post", back_populates="platform")
    platform_reports: Mapped[list["PlatformReport"]] = relationship("PlatformReport", back_populates="platform")

