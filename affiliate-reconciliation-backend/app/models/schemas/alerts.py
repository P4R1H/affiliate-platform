"""
Pydantic schemas for alert management.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class AlertRead(BaseModel):
    id: int
    reconciliation_log_id: int
    alert_type: str = Field(description="HIGH_DISCREPANCY, MISSING_DATA, etc.")
    title: str
    message: str
    threshold_breached: Optional[Dict[str, Any]]
    status: str = Field(description="OPEN or RESOLVED")
    resolved_by: Optional[str]
    resolved_at: Optional[datetime]
    resolution_notes: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class AlertResolve(BaseModel):
    """
    Schema for resolving alerts.
    """
    resolved_by: str = Field(min_length=1, max_length=100)
    resolution_notes: Optional[str] = Field(None, max_length=1000)

