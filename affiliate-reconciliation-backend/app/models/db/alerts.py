from __future__ import annotations
"""SQLAlchemy model for alerts generated when significant discrepancies are found."""
import enum
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column

if TYPE_CHECKING:  # pragma: no cover
    from .reconciliation_logs import ReconciliationLog
from sqlalchemy.sql import func
from app.database import Base
from .enums import AlertSeverity, AlertCategory

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
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reconciliation_log_id: Mapped[int] = mapped_column(Integer, ForeignKey("reconciliation_logs.id"), nullable=False)
    # Denormalised for faster querying / filtering
    affiliate_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("affiliates.id"), nullable=True, index=True)
    platform_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("platforms.id"), nullable=True, index=True)
    alert_type: Mapped[AlertType] = mapped_column(Enum(AlertType), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    threshold_breached: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    category: Mapped[AlertCategory] = mapped_column(Enum(AlertCategory), default=AlertCategory.DATA_QUALITY, index=True)
    severity: Mapped[AlertSeverity] = mapped_column(Enum(AlertSeverity), default=AlertSeverity.LOW, index=True)
    status: Mapped[AlertStatus] = mapped_column(Enum(AlertStatus), default=AlertStatus.OPEN, index=True)
    resolved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    resolved_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    reconciliation_log: Mapped["ReconciliationLog"] = relationship("ReconciliationLog", back_populates="alert")
