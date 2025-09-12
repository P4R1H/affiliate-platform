"""
Base schemas used across the application.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class UnifiedMetrics(BaseModel):
    """
    Standardized metrics schema that all platforms map to.
    This is our internal common format.
    """
    views: int = Field(ge=0, description="Number of views/impressions")
    clicks: int = Field(ge=0, description="Number of clicks")
    conversions: int = Field(ge=0, description="Number of conversions")
    
    post_url: str = Field(description="URL of the post")
    platform_name: str = Field(description="Platform where post was made")
    timestamp: datetime = Field(description="When metrics were captured")
    source: str = Field(description="Source of data: 'affiliate_claim' or 'platform_api'")

class ResponseBase(BaseModel):
    """
    Base response format for API endpoints.
    """
    success: bool = True
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

