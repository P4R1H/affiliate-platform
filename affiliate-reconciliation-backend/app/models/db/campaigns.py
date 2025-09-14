from __future__ import annotations
"""SQLAlchemy model for advertising campaigns."""
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, Date, DateTime, Numeric, Enum, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column

if TYPE_CHECKING:  # pragma: no cover
    from .platforms import Platform
    from .posts import Post
    from .clients import Client
    from .users import User
from sqlalchemy.sql import func
from app.database import Base
from .platforms import campaign_platform_association
from .enums import CampaignStatus

class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    start_date: Mapped[Date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    impression_cap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cpm: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[CampaignStatus] = mapped_column(Enum(CampaignStatus), default=CampaignStatus.ACTIVE, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="campaigns")
    creator: Mapped["User"] = relationship("User", back_populates="created_campaigns")
    platforms: Mapped[list["Platform"]] = relationship(
        "Platform", secondary=campaign_platform_association, back_populates="campaigns"
    )
    posts: Mapped[list["Post"]] = relationship("Post", back_populates="campaign")

