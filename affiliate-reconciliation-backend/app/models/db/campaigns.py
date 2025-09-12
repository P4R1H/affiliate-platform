"""
SQLAlchemy model for advertising campaigns.
"""
from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
from .platforms import campaign_platform_association

class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    advertiser_name = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    impression_cap = Column(Integer, nullable=True)
    cpm = Column(Numeric(10, 2), nullable=True)
    status = Column(String, default="active")  # active, paused, ended
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    platforms = relationship(
        "Platform",
        secondary=campaign_platform_association,
        back_populates="campaigns"
    )
    posts = relationship("Post", back_populates="campaign")

