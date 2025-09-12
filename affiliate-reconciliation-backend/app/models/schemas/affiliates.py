"""
Pydantic schemas for affiliate-related operations.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, EmailStr
from .base import UnifiedMetrics

class AffiliateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    discord_user_id: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "name": "John Doe",
                "email": "john@example.com",
                "discord_user_id": "johndoe#1234"
            }
        }

class AffiliateRead(BaseModel):
    id: int
    name: str
    email: str
    discord_user_id: Optional[str]
    api_key: Optional[str]
    is_active: bool
    trust_score: float = Field(ge=0.0, le=1.0)
    total_submissions: int
    accurate_submissions: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class AffiliateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    discord_user_id: Optional[str] = None
    is_active: Optional[bool] = None

class AffiliatePostSubmission(BaseModel):
    """
    Schema for when affiliates submit a new post with their claimed metrics.
    This is the main entry point for affiliate data.
    """
    campaign_id: int = Field(gt=0)
    platform_id: int = Field(gt=0)
    post_url: str = Field(min_length=1, description="URL of the post")
    
    # Optional post metadata
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)
    
    # Claimed metrics
    claimed_views: int = Field(ge=0)
    claimed_clicks: int = Field(ge=0) 
    claimed_conversions: int = Field(ge=0)
    
    # Evidence and submission method
    evidence_data: Optional[Dict[str, Any]] = Field(None, description="Screenshots, links, additional data")
    submission_method: str = Field(description="API or DISCORD")
    
    class Config:
        schema_extra = {
            "example": {
                "campaign_id": 1,
                "platform_id": 2,
                "post_url": "https://reddit.com/r/example/comments/123456",
                "title": "Amazing Product Review",
                "claimed_views": 1500,
                "claimed_clicks": 75,
                "claimed_conversions": 3,
                "evidence_data": {
                    "screenshot_urls": ["https://imgur.com/abc123"],
                    "additional_links": ["https://analytics.example.com/report/456"]
                },
                "submission_method": "API"
            }
        }
