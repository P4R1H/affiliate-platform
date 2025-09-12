from __future__ import annotations
"""SQLAlchemy model for affiliate partners."""
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, DateTime, Boolean, Numeric
from sqlalchemy.orm import relationship, Mapped, mapped_column

if TYPE_CHECKING:  # pragma: no cover
    from .posts import Post
from sqlalchemy.sql import func
from app.database import Base

class Affiliate(Base):
    __tablename__ = "affiliates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    discord_user_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
#   api_key: Mapped[str | None] = mapped_column(String, unique=True, nullable=True) 
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    trust_score: Mapped[float] = mapped_column(Numeric(3, 2), default=1.00)
    last_trust_update: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_submissions: Mapped[int] = mapped_column(Integer, default=0)
    accurate_submissions: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    posts: Mapped[list["Post"]] = relationship("Post", back_populates="affiliate")
