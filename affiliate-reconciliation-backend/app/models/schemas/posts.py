"""
Pydantic schemas for post management.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class PostCreate(BaseModel):
    """
    Internal schema for creating posts (used by the system, not directly by affiliates).
    """
    campaign_id: int = Field(gt=0)
    affiliate_id: int = Field(gt=0)
    platform_id: int = Field(gt=0)
    url: str = Field(min_length=1)
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)

class PostRead(BaseModel):
    id: int
    campaign_id: int
    affiliate_id: int
    platform_id: int
    url: str
    title: Optional[str]
    description: Optional[str]
    is_reconciled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

