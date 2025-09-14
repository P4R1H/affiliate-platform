"""
Pydantic schemas for user-related operations.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator
from ..db.enums import UserRole
from ..db.affiliate_reports import SubmissionMethod 

class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    role: UserRole
    discord_user_id: Optional[str] = None
    client_id: Optional[int] = None
    
    @field_validator('client_id')
    @classmethod
    def validate_client_id(cls, v, info):
        role = info.data.get('role')
        if role == UserRole.CLIENT and v is None:
            raise ValueError('client_id is required for CLIENT role users')
        if role != UserRole.CLIENT and v is not None:
            raise ValueError('client_id must be None for non-CLIENT role users')
        return v
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "John Doe",
            "email": "john@example.com",
            "role": "AFFILIATE",
            "discord_user_id": "johndoe#1234"
        }
    })

class UserCreateAffiliate(BaseModel):
    """Specialized schema for creating affiliate users."""
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    discord_user_id: Optional[str] = None
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "Jane Smith",
            "email": "jane@example.com",
            "discord_user_id": "janesmith#5678"
        }
    })

class UserCreateClient(BaseModel):
    """Specialized schema for creating client users."""
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    client_id: int = Field(gt=0)
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "Client Admin",
            "email": "admin@client.com",
            "client_id": 1
        }
    })

class UserRead(BaseModel):
    id: int
    name: str
    email: str
    discord_user_id: Optional[str]
    api_key: Optional[str]
    is_active: bool
    role: UserRole
    client_id: Optional[int]
    trust_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    total_submissions: int
    accurate_submissions: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    discord_user_id: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None
    client_id: Optional[int] = None
    
    @field_validator('client_id')
    @classmethod
    def validate_client_id(cls, v, info):
        role = info.data.get('role')
        if role == UserRole.CLIENT and v is None:
            raise ValueError('client_id is required for CLIENT role users')
        if role and role != UserRole.CLIENT and v is not None:
            raise ValueError('client_id must be None for non-CLIENT role users')
        return v

class UserPostSubmission(BaseModel):
    """
    Schema for when users submit a new post with their claimed metrics.
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
    submission_method: SubmissionMethod = Field(description="API or DISCORD")
    
    model_config = ConfigDict(json_schema_extra={
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
    })