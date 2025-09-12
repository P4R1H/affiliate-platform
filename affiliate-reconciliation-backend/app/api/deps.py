"""
FastAPI dependencies for authentication, database sessions, and common validations.
Provides reusable dependency functions for consistent API behavior.
"""
from typing import Generator, Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.db import Affiliate, Platform, Campaign
from app.utils import get_logger

logger = get_logger(__name__)
security = HTTPBearer()

def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency.
    Ensures proper session lifecycle management with automatic cleanup.
    
    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error("Database session error", error=str(e), exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()

def get_current_affiliate(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Affiliate:
    """
    Extract and validate affiliate from API key.
    Used for affiliate-specific endpoints that require authentication.
    
    Args:
        credentials: Bearer token credentials from Authorization header
        db: Database session
        
    Returns:
        Affiliate: Authenticated affiliate object
        
    Raises:
        HTTPException: If API key is invalid or affiliate is inactive
    """
    api_key = credentials.credentials
    
    logger.debug(
        "Affiliate authentication attempt",
        api_key_prefix=api_key[:10] + "..." if len(api_key) > 10 else api_key
    )
    
    affiliate = db.query(Affiliate).filter(
        Affiliate.api_key == api_key,
        Affiliate.is_active == True
    ).first()
    
    if not affiliate:
        logger.warning(
            "Authentication failed: invalid or inactive API key",
            api_key_prefix=api_key[:10] + "..." if len(api_key) > 10 else api_key
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.info(
        "Affiliate authenticated successfully",
        affiliate_id=affiliate.id,
        affiliate_name=affiliate.name
    )
    
    return affiliate

def validate_platform_exists(platform_id: int, db: Session = Depends(get_db)) -> Platform:
    """
    Validate that a platform exists and is active.
    
    Args:
        platform_id: Platform ID to validate
        db: Database session
        
    Returns:
        Platform: Validated platform object
        
    Raises:
        HTTPException: If platform doesn't exist or is inactive
    """
    platform = db.query(Platform).filter(
        Platform.id == platform_id,
        Platform.is_active == True
    ).first()
    
    if not platform:
        logger.warning(
            "Platform validation failed",
            platform_id=platform_id
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Platform with id {platform_id} not found or inactive"
        )
    
    logger.debug(
        "Platform validated successfully",
        platform_id=platform_id,
        platform_name=platform.name
    )
    
    return platform

def validate_campaign_exists(campaign_id: int, db: Session = Depends(get_db)) -> Campaign:
    """
    Validate that a campaign exists and is active.
    
    Args:
        campaign_id: Campaign ID to validate
        db: Database session
        
    Returns:
        Campaign: Validated campaign object
        
    Raises:
        HTTPException: If campaign doesn't exist or is not active
    """
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.status == "active"
    ).first()
    
    if not campaign:
        logger.warning(
            "Campaign validation failed",
            campaign_id=campaign_id
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign with id {campaign_id} not found or not active"
        )
    
    logger.debug(
        "Campaign validated successfully",
        campaign_id=campaign_id,
        campaign_name=campaign.name
    )
    
    return campaign

def validate_campaign_platform_relationship(
    campaign: Campaign,
    platform: Platform
) -> None:
    """
    Validate that a platform is assigned to a campaign.
    
    Args:
        campaign: Campaign object
        platform: Platform object
        
    Raises:
        HTTPException: If platform is not assigned to campaign
    """
    if platform not in campaign.platforms:
        logger.warning(
            "Campaign-platform relationship validation failed",
            campaign_id=campaign.id,
            platform_id=platform.id,
            campaign_name=campaign.name,
            platform_name=platform.name
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Platform '{platform.name}' is not assigned to campaign '{campaign.name}'"
        )
    
    logger.debug(
        "Campaign-platform relationship validated",
        campaign_id=campaign.id,
        platform_id=platform.id
    )

def get_pagination_params(
    limit: int = 50,
    offset: int = 0
) -> dict:
    """
    Validate and return pagination parameters.
    
    Args:
        limit: Maximum number of items to return (1-500)
        offset: Number of items to skip (>= 0)
        
    Returns:
        dict: Validated pagination parameters
        
    Raises:
        HTTPException: If parameters are invalid
    """
    if limit < 1 or limit > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 500"
        )
    
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Offset must be >= 0"
        )
    
    return {"limit": limit, "offset": offset}

def check_admin_access(
    x_admin_key: Optional[str] = Header(None)
) -> bool:
    """
    Check if request has admin access.
    Used for admin-only endpoints like campaign creation.
    
    Args:
        x_admin_key: Admin key from X-Admin-Key header
        
    Returns:
        bool: True if admin access granted
        
    Raises:
        HTTPException: If admin key is invalid
    """
    # In production, this would check against a secure admin key
    # For demo purposes, we'll use a simple check
    expected_admin_key = "admin_demo_key_123"
    
    if not x_admin_key or x_admin_key != expected_admin_key:
        logger.warning(
            "Admin access denied",
            provided_key=x_admin_key[:10] + "..." if x_admin_key and len(x_admin_key) > 10 else x_admin_key
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    logger.info("Admin access granted")
    return True

