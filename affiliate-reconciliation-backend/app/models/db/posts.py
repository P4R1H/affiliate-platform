"""
SQLAlchemy model for individual posts submitted by affiliates.
Each post represents a single piece of content (link) posted by an affiliate for a campaign.
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign Keys
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    affiliate_id = Column(Integer, ForeignKey("affiliates.id"), nullable=False)
    platform_id = Column(Integer, ForeignKey("platforms.id"), nullable=False)
    
    # Post details
    url = Column(String, nullable=False, index=True)  # The actual post URL
    title = Column(String, nullable=True)  # Optional post title
    description = Column(String, nullable=True)  # Optional post description
    
    # Status tracking
    is_reconciled = Column(Boolean, default=False, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    campaign = relationship("Campaign", back_populates="posts")
    affiliate = relationship("Affiliate", back_populates="posts")
    platform = relationship("Platform", back_populates="posts")
    
    # One post can have multiple reports (snapshots over time)
    affiliate_reports = relationship("AffiliateReport", back_populates="post")
    platform_reports = relationship("PlatformReport", back_populates="post")

    # Constraints - Prevent duplicate posts from same affiliate
    __table_args__ = (
        UniqueConstraint('campaign_id', 'platform_id', 'url', 'affiliate_id', 
                        name='unique_affiliate_post_per_campaign'),
    )

