"""
SQLAlchemy model for reports submitted by affiliates (their claims).
Now linked to individual posts - each report is a snapshot of metrics for a specific post.
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
    
    # Foreign Keys - now linked to specific post
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    
    # Claimed metrics at time of submission
    claimed_views = Column(Integer, default=0)
    claimed_clicks = Column(Integer, default=0)
    claimed_conversions = Column(Integer, default=0)

    # Submission details
    evidence_data = Column(JSON, nullable=True)  # Links, Discord messages, etc.
    submission_method = Column(Enum(SubmissionMethod), nullable=False)
    status = Column(Enum(ReportStatus), default=ReportStatus.PENDING, index=True)
    
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    post = relationship("Post", back_populates="affiliate_reports")
    reconciliation_log = relationship("ReconciliationLog", back_populates="affiliate_report", uselist=False)
