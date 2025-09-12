"""
SQLAlchemy model for reports submitted by affiliates (their claims).
"""
import enum
from sqlalchemy import Column, Integer, String, Date, ForeignKey, DateTime, Enum, Numeric, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class SubmissionMethod(str, enum.Enum):
    API = "API"
    DISCORD = "DISCORD"

class ReportStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"

class AffiliateReport(Base):
    __tablename__ = "affiliate_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_date = Column(Date, nullable=False, index=True)
    
    # Foreign Keys
    affiliate_id = Column(Integer, ForeignKey("affiliates.id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    platform_id = Column(Integer, ForeignKey("platforms.id"), nullable=False)

    # Claimed metrics
    claimed_clicks = Column(Integer, default=0)
    claimed_views = Column(Integer, default=0)
    claimed_conversions = Column(Integer, default=0)
    claimed_revenue = Column(Numeric(10, 2), default=0.00)

    # Submission details
    evidence_data = Column(JSON, nullable=True)  # Screenshots, links, Discord messages
    submission_method = Column(Enum(SubmissionMethod), nullable=False)
    status = Column(Enum(ReportStatus), default=ReportStatus.PENDING, index=True)
    
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    affiliate = relationship("Affiliate", back_populates="reports")
    campaign = relationship("Campaign", back_populates="affiliate_reports")
    platform = relationship("Platform", back_populates="affiliate_reports")
    reconciliation_log = relationship("ReconciliationLog", back_populates="affiliate_report", uselist=False)

