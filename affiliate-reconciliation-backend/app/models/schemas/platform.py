"""
Pydantic schemas for platform integration responses.
Contains both raw platform-specific response schemas and unified output schema.
"""
from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, ConfigDict
from .base import UnifiedMetrics

class RedditAPIResponse(BaseModel):
    """Raw Reddit API response schema."""
    ups: int = Field(ge=0, description="Number of upvotes")
    downs: int = Field(ge=0, description="Number of downvotes") 
    score: int = Field(description="Net score (ups - downs)")
    num_comments: int = Field(ge=0, description="Number of comments")
    upvote_ratio: float = Field(ge=0, le=1, description="Ratio of upvotes")
    awards: Optional[int] = Field(0, ge=0, description="Number of awards")
    gilded: Optional[int] = Field(0, ge=0, description="Number of gold awards")
    total_awards_received: Optional[int] = Field(0, ge=0)
    subreddit: Optional[str] = None
    permalink: Optional[str] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "ups": 1500,
            "downs": 100,
            "score": 1400,
            "num_comments": 75,
            "upvote_ratio": 0.94,
            "awards": 5,
            "gilded": 2,
            "total_awards_received": 7,
            "subreddit": "technology",
            "permalink": "/r/technology/comments/123abc/title/"
        }
    })

class InstagramAPIResponse(BaseModel):
    """Raw Instagram API response schema.

    Assumptions for mock implementation:
    - impressions and reach are always produced (we treat them as required for downstream mapping to unified 'views').
    - play_count may be absent for image/carousel posts.
    - saved, profile_visits, website_clicks are secondary/interaction metrics and may be absent.
    """
    like_count: int = Field(ge=0, description="Number of likes")
    comment_count: int = Field(ge=0, description="Number of comments")
    impressions: int = Field(ge=0, description="Number of impressions")
    reach: int = Field(ge=0, description="Post reach")
    play_count: Optional[int] = Field(None, ge=0, description="Video play count (only for reels/videos)")
    saved: Optional[int] = Field(None, ge=0, description="Number of saves")
    profile_visits: Optional[int] = Field(None, ge=0, description="Profile visits from post")
    website_clicks: Optional[int] = Field(None, ge=0, description="Website clicks")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "like_count": 1200,
            "comment_count": 45,
            "play_count": 5000,
            "reach": 8000,
            "impressions": 12000,
            "saved": 150,
            "profile_visits": 85,
            "website_clicks": 25
        }
    })

class TikTokAPIResponse(BaseModel):
    """Raw TikTok API response schema."""
    play_count: int = Field(ge=0, description="Number of plays")
    like_count: int = Field(ge=0, description="Number of likes")
    comment_count: int = Field(ge=0, description="Number of comments")
    share_count: int = Field(ge=0, description="Number of shares")
    view_count: Optional[int] = Field(None, ge=0, description="View count (if available)")
    profile_views: Optional[int] = Field(None, ge=0, description="Profile views from video")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "play_count": 50000,
            "like_count": 3200,
            "comment_count": 150,
            "share_count": 280,
            "view_count": 48000,
            "profile_views": 450
        }
    })

class YouTubeAPIResponse(BaseModel):
    """Raw YouTube API response schema."""
    view_count: int = Field(ge=0, description="Number of views")
    like_count: int = Field(ge=0, description="Number of likes")
    comment_count: int = Field(ge=0, description="Number of comments")
    subscriber_count_gained: Optional[int] = Field(None, ge=0, description="Subscribers gained")
    average_view_duration: Optional[float] = Field(None, ge=0, description="Average view duration in seconds")
    click_through_rate: Optional[float] = Field(None, ge=0, le=1, description="Thumbnail click-through rate")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "view_count": 25000,
            "like_count": 1800,
            "comment_count": 95,
            "subscriber_count_gained": 45,
            "average_view_duration": 180.5,
            "click_through_rate": 0.08
        }
    })

class XAPIResponse(BaseModel):
    """Raw X/Twitter API response schema."""
    retweet_count: int = Field(ge=0, description="Number of retweets")
    like_count: int = Field(ge=0, description="Number of likes")
    reply_count: int = Field(ge=0, description="Number of replies")
    quote_count: int = Field(ge=0, description="Number of quote tweets")
    impression_count: Optional[int] = Field(None, ge=0, description="Number of impressions")
    bookmark_count: Optional[int] = Field(None, ge=0, description="Number of bookmarks")
    profile_clicks: Optional[int] = Field(None, ge=0, description="Profile clicks")
    url_link_clicks: Optional[int] = Field(None, ge=0, description="URL link clicks")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "retweet_count": 450,
            "like_count": 2800,
            "reply_count": 120,
            "quote_count": 85,
            "impression_count": 45000,
            "bookmark_count": 180,
            "profile_clicks": 95,
            "url_link_clicks": 220
        }
    })

class PlatformAPIResponse(BaseModel):
    """
    Unified schema for platform API responses.
    All platform integrations map their raw response to this standardized format.
    """
    post_url: str = Field(description="Clean/canonical URL of the post")
    platform_name: str = Field(description="Platform name (lowercase)")
    raw_response: Dict[str, Any] = Field(description="Complete raw API response for debugging")

    views: int = Field(ge=0, description="Views/impressions/plays")
    clicks: int = Field(ge=0, description="Clicks/taps on post or links") 
    conversions: int = Field(ge=0, description="Actions taken (follows, saves, etc.)")
    spend: Optional[float] = Field(None, ge=0, description="Ad spend if applicable")

    likes: Optional[int] = Field(None, ge=0, description="Likes/reactions")
    comments: Optional[int] = Field(None, ge=0, description="Comments/replies")
    shares: Optional[int] = Field(None, ge=0, description="Shares/retweets")

    fetched_at: datetime = Field(default_factory=datetime.utcnow, description="When data was fetched")
    api_version: Optional[str] = Field(None, description="API version used")
    rate_limit_remaining: Optional[int] = Field(None, description="API rate limit remaining")
    cache_hit: bool = Field(False, description="Whether data came from cache")

    def to_unified_metrics(self) -> UnifiedMetrics:
        return UnifiedMetrics(
            views=self.views,
            clicks=self.clicks,
            conversions=self.conversions,
            post_url=self.post_url,
            platform_name=self.platform_name,
            timestamp=self.fetched_at,
            source="platform_api"
        )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "post_url": "https://reddit.com/r/technology/comments/123456/awesome_post",
            "platform_name": "reddit",
            "raw_response": {"data": {"ups": 1500, "num_comments": 75, "score": 1450, "upvote_ratio": 0.96}},
            "views": 1500,
            "clicks": 75,
            "conversions": 12,
            "likes": 1500,
            "comments": 75,
            "shares": 25,
            "fetched_at": "2025-09-13T10:30:00Z",
            "api_version": "v1.0",
            "rate_limit_remaining": 995,
            "cache_hit": False
        }
    })

class PlatformError(BaseModel):
    """Schema for platform integration errors."""
    platform_name: str
    error_type: str = Field(description="API_ERROR, RATE_LIMITED, NOT_FOUND, etc.")
    error_message: str
    post_url: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    retry_after: Optional[int] = Field(None, description="Seconds to wait before retry")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "platform_name": "reddit",
            "error_type": "RATE_LIMITED",
            "error_message": "Rate limit exceeded. Try again in 60 seconds.",
            "post_url": "https://reddit.com/r/test/comments/123",
            "timestamp": "2025-09-13T10:30:00Z",
            "retry_after": 60
        }
    })