"""
SQLAlchemy model for alerts generated when significant discrepancies are found.
"""
import enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class AlertStatus(str, enum.Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"

class AlertType(str, enum.Enum):
    HIGH_DISCREPANCY = "HIGH_DISCREPANCY"
    MISSING_DATA = "MISSING_DATA" 
    SUSPICIOUS_CLAIM = "SUSPICIOUS_CLAIM"
    SYSTEM_ERROR = "SYSTEM_ERROR"

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    reconciliation_log_id = Column(Integer, ForeignKey("reconciliation_logs.id"), nullable=False)
    
    alert_type = Column(Enum(AlertType), nullable=False)
    title = Column(String, nullable=False)  # "High Click Discrepancy Detected"
    message = Column(Text, nullable=False)  # Detailed description
    threshold_breached = Column(JSON, nullable=True)  # What threshold was crossed
    
    status = Column(Enum(AlertStatus), default=AlertStatus.OPEN, index=True)
    resolved_by = Column(String, nullable=True)  # Who resolved it
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    reconciliation_log = relationship("ReconciliationLog", back_populates="alert")