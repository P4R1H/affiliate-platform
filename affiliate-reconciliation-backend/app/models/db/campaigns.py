from __future__ import annotations
"""SQLAlchemy model for advertising campaigns."""
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, Date, DateTime, Numeric, Enum
from sqlalchemy.orm import relationship, Mapped, mapped_column

if TYPE_CHECKING:  # pragma: no cover
    from .platforms import Platform
    from .posts import Post
from sqlalchemy.sql import func
from app.database import Base
from .platforms import campaign_platform_association
from .enums import CampaignStatus

class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    advertiser_name: Mapped[str] = mapped_column(String)
    start_date: Mapped[Date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    impression_cap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cpm: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[CampaignStatus] = mapped_column(Enum(CampaignStatus), default=CampaignStatus.ACTIVE, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    platforms: Mapped[list["Platform"]] = relationship(
        "Platform", secondary=campaign_platform_association, back_populates="campaigns"
    )
    posts: Mapped[list["Post"]] = relationship("Post", back_populates="campaign")

