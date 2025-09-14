from __future__ import annotations
"""SQLAlchemy model for client organizations."""
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, DateTime
from sqlalchemy.orm import relationship, Mapped, mapped_column

if TYPE_CHECKING:  # pragma: no cover
    from .campaigns import Campaign
    from .users import User

from sqlalchemy.sql import func
from app.database import Base


class Client(Base):
    __tablename__ = "clients"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="client")
    campaigns: Mapped[list["Campaign"]] = relationship("Campaign", back_populates="client")