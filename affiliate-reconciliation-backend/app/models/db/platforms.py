"""
SQLAlchemy model for advertising platforms (e.g., Reddit, Meta, Instagram).
"""
from sqlalchemy import Column, Integer, String, DateTime, Table, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
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

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    api_base_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    api_config = Column(JSON, nullable=True)  # Store API keys, rate limits, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    campaigns = relationship(
        "Campaign",
        secondary=campaign_platform_association,
        back_populates="platforms"
    )
    posts = relationship("Post", back_populates="platform")
    platform_reports = relationship("PlatformReport", back_populates="platform")

