"""
SQLAlchemy model for the 'source of truth' data fetched from advertising platform APIs.
"""
from sqlalchemy import Column, Integer, Numeric, Date, ForeignKey, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class PlatformReport(Base):
    __tablename__ = "platform_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_date = Column(Date, nullable=False, index=True)

    # Foreign Keys
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    platform_id = Column(Integer, ForeignKey("platforms.id"), nullable=False)
    
    # Platform metrics (source of truth)
    clicks = Column(Integer, default=0)
    views = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    spend = Column(Numeric(10, 2), default=0.00)
    revenue = Column(Numeric(10, 2), default=0.00)

    # Metadata
    raw_data = Column(JSON, nullable=True)  # Store complete API response
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    campaign = relationship("Campaign", back_populates="platform_reports")
    platform = relationship("Platform", back_populates="platform_reports")
    reconciliation_logs = relationship("ReconciliationLog", back_populates="platform_report")

    # Constraints
    __table_args__ = (
        UniqueConstraint('campaign_id', 'platform_id', 'report_date', name='unique_campaign_platform_date'),
    )