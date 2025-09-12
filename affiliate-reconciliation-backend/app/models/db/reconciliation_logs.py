"""
SQLAlchemy model for the logs generated during the reconciliation process.
Now operates per-post instead of aggregate reconciliation runs.
"""
import enum
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Enum, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class DiscrepancyLevel(str, enum.Enum):
    LOW = "LOW"        # < 5% difference
    MEDIUM = "MEDIUM"  # 5-20% difference  
    HIGH = "HIGH"      # > 20% difference

class ReconciliationStatus(str, enum.Enum):
    MATCHED = "MATCHED"
    DISCREPANCY = "DISCREPANCY" 
    MISSING_PLATFORM_DATA = "MISSING_PLATFORM_DATA"
    AFFILIATE_OVERCLAIMED = "AFFILIATE_OVERCLAIMED"  # A >> B case

class ReconciliationLog(Base):
    __tablename__ = "reconciliation_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    # What we're comparing - specific affiliate report vs platform report
    affiliate_report_id = Column(Integer, ForeignKey("affiliate_reports.id"), nullable=False, unique=True)
    platform_report_id = Column(Integer, ForeignKey("platform_reports.id"), nullable=True)  # NULL if missing platform data
    
    # Results
    status = Column(Enum(ReconciliationStatus), nullable=False, index=True)
    discrepancy_level = Column(Enum(DiscrepancyLevel), nullable=True, index=True)
    
    # Absolute differences (negative = affiliate claimed less than platform reported)
    views_discrepancy = Column(Integer, default=0)
    clicks_discrepancy = Column(Integer, default=0) 
    conversions_discrepancy = Column(Integer, default=0)
    
    # Percentage differences for easy thresholding
    views_diff_pct = Column(Numeric(5, 2), nullable=True)  # e.g., 15.25 for 15.25%
    clicks_diff_pct = Column(Numeric(5, 2), nullable=True)
    conversions_diff_pct = Column(Numeric(5, 2), nullable=True)
    
    notes = Column(Text, nullable=True)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    affiliate_report = relationship("AffiliateReport", back_populates="reconciliation_log")
    platform_report = relationship("PlatformReport", back_populates="reconciliation_logs")
    alert = relationship("Alert", back_populates="reconciliation_log", uselist=False)

