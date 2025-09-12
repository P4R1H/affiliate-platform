"""
SQLAlchemy model for the 'source of truth' data fetched from advertising platform APIs.
Now linked to individual posts - each report is platform data for a specific post.
"""
from sqlalchemy import Column, Integer, Numeric, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class PlatformReport(Base):
    __tablename__ = "platform_reports"

    id = Column(Integer, primary_key=True, index=True)

    # Foreign Keys - now linked to specific post
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    platform_id = Column(Integer, ForeignKey("platforms.id"), nullable=False)
    
    # Platform metrics (source of truth) at time of fetch
    views = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    spend = Column(Numeric(10, 2), default=0.00)

    # Metadata
    raw_data = Column(JSON, nullable=True)  # Store complete API response
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    post = relationship("Post", back_populates="platform_reports")
    platform = relationship("Platform", back_populates="platform_reports")
    reconciliation_logs = relationship("ReconciliationLog", back_populates="platform_report")

