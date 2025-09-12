"""
SQLAlchemy model for affiliate partners.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Affiliate(Base):
    __tablename__ = "affiliates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    discord_user_id = Column(String, nullable=True, unique=True)
    api_key = Column(String, unique=True, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Trust scoring fields
    trust_score = Column(Numeric(3,2), default=1.00)  # 0.00 to 1.00
    last_trust_update = Column(DateTime(timezone=True), nullable=True)
    total_submissions = Column(Integer, default=0)
    accurate_submissions = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    posts = relationship("Post", back_populates="affiliate")
