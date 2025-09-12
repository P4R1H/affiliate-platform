"""
Pydantic schemas for platform integration responses.
"""
from datetime import datetime
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from .base import UnifiedMetrics

class PlatformAPIResponse(BaseModel):
    """
    Flexible schema for platform API responses.
    Each platform integration will map their response to UnifiedMetrics.
    """
    post_url: str
    platform_name: str
    raw_response: Dict[str, Any] = Field(description="Complete API response for debugging")
    
    # Standardized metrics (mapped from raw_response)
    views: int = Field(ge=0)
    clicks: int = Field(ge=0) 
    conversions: int = Field(ge=0)
    spend: Optional[float] = Field(None, ge=0)
    
    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    api_version: Optional[str] = None
    rate_limit_remaining: Optional[int] = None
    
    def to_unified_metrics(self) -> UnifiedMetrics:
        """
        Convert platform response to unified metrics format.
        """
        return UnifiedMetrics(
            views=self.views,
            clicks=self.clicks,
            conversions=self.conversions,
            post_url=self.post_url,
            platform_name=self.platform_name,
            timestamp=self.fetched_at,
            source="platform_api"
        )
    
    class Config:
        schema_extra = {
            "example": {
                "post_url": "https://reddit.com/r/example/comments/123456",
                "platform_name": "reddit",
                "raw_response": {
                    "data": {
                        "ups": 1500,
                        "num_comments": 75,
                        "score": 1450,
                        "upvote_ratio": 0.96
                    }
                },
                "views": 1500,
                "clicks": 75,
                "conversions": 3,
                "fetched_at": "2025-09-12T10:30:00Z",
                "api_version": "v1.0"
            }
        }