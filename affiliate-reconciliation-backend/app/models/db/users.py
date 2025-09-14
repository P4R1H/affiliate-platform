from __future__ import annotations
"""SQLAlchemy model for users (affiliates and clients)."""
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, DateTime, Boolean, Numeric, Enum, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column

if TYPE_CHECKING:  # pragma: no cover
    from .posts import Post
    from .clients import Client
    from .campaigns import Campaign
from sqlalchemy.sql import func
from app.database import Base
from .enums import UserRole

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    discord_user_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    api_key: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.AFFILIATE, index=True)
    
    # Client relationship - only for CLIENT role users
    client_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("clients.id"), nullable=True, index=True)

    # Affiliate-specific fields (nullable for CLIENT users)
    trust_score: Mapped[float | None] = mapped_column(Numeric(3, 2), default=0.50, nullable=True)
    last_trust_update: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_submissions: Mapped[int] = mapped_column(Integer, default=0)
    accurate_submissions: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    client: Mapped["Client | None"] = relationship("Client", back_populates="users")
    posts: Mapped[list["Post"]] = relationship("Post", back_populates="user")
    created_campaigns: Mapped[list["Campaign"]] = relationship("Campaign", back_populates="creator")
    
    # Check constraints for role-based validation
    __table_args__ = (
        CheckConstraint(
            "role != 'CLIENT' OR client_id IS NOT NULL",
            name="client_users_must_have_client_id"
        ),
        CheckConstraint(
            "role = 'CLIENT' OR client_id IS NULL",
            name="non_client_users_no_client_id"
        ),
    )
