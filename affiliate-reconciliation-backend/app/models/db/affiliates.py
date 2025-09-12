"""
SQLAlchemy model for affiliate partners.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
from .platforms import affiliate_platform_association

class Affiliate(Base):
    __tablename__ = "affiliates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    discord_user_id = Column(String, nullable=True, unique=True)
    api_key = Column(String, unique=True, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    reports = relationship("AffiliateReport", back_populates="affiliate")
    platforms = relationship(
        "Platform",
        secondary=affiliate_platform_association,
        back_populates="affiliates"
    )
