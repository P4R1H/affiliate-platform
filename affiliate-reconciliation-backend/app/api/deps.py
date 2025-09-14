"""
Dependencies for authentication, database sessions, and common validations.
"""
from typing import Generator, Optional, List
from fastapi import Depends, HTTPException, status, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.db import User, Platform, Campaign, Client
from app.models.db.enums import UserRole
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

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Extract and validate user from API key.
    Used for user-specific endpoints that require authentication.
    
    Args:
        credentials: Bearer token credentials from Authorization header
        db: Database session
        
    Returns:
        User: Authenticated user object
        
    Raises:
        HTTPException: If API key is invalid or user is inactive
    """
    api_key = credentials.credentials
    
    logger.debug(
        "User authentication attempt",
        api_key_prefix=api_key[:10] + "..." if len(api_key) > 10 else api_key
    )
    
    user = db.query(User).filter(
        User.api_key == api_key,
        User.is_active == True
    ).first()
    
    if not user:
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
        "User authenticated successfully",
        user_id=user.id,
        user_name=user.name,
        user_role=user.role
    )
    
    return user

# Legacy alias for backward compatibility
def get_current_affiliate(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Legacy function for backward compatibility.
    Now returns User but only for AFFILIATE role users.
    """
    user = get_current_user(credentials, db)
    
    if user.role != UserRole.AFFILIATE:
        logger.warning(
            "Access denied: non-affiliate user attempted to use affiliate endpoint",
            user_id=user.id,
            user_role=user.role
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only available to affiliate users"
        )
    
    return user

def require_role(allowed_roles: List[UserRole]):
    """
    Factory function to create a dependency that requires specific user roles.
    
    Args:
        allowed_roles: List of allowed user roles
        
    Returns:
        Dependency function that validates user role
    """
    def role_dependency(
        current_user: User = Depends(get_current_user)
    ) -> User:
        if current_user.role not in allowed_roles:
            logger.warning(
                "Access denied: insufficient role",
                user_id=current_user.id,
                user_role=current_user.role,
                required_roles=[role.value for role in allowed_roles]
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[role.value for role in allowed_roles]}"
            )
        return current_user
    
    return role_dependency

def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency that requires ADMIN role.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User: Admin user object
        
    Raises:
        HTTPException: If user is not an admin
    """
    if current_user.role != UserRole.ADMIN:
        logger.warning(
            "Access denied: admin required",
            user_id=current_user.id,
            user_role=current_user.role
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return current_user

def get_current_client_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency that returns a client user with client relationship preloaded.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        User: Client user with client relationship loaded
        
    Raises:
        HTTPException: If user is not a client user
    """
    if current_user.role != UserRole.CLIENT:
        logger.warning(
            "Access denied: client role required",
            user_id=current_user.id,
            user_role=current_user.role
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client access required"
        )
    
    # Ensure client relationship is loaded
    if not current_user.client:
        db.refresh(current_user, ['client'])
    
    return current_user

def require_client_access(client_id: int):
    """
    Factory function to create a dependency that validates client ownership.
    
    Args:
        client_id: ID of the client to validate access for
        
    Returns:
        Dependency function that validates client access
    """
    def client_access_dependency(
        current_user: User = Depends(get_current_user)
    ) -> User:
        # Admin users have access to all clients
        if current_user.role == UserRole.ADMIN:
            return current_user
        
        # Client users can only access their own client
        if current_user.role == UserRole.CLIENT:
            if current_user.client_id != client_id:
                logger.warning(
                    "Access denied: client access violation",
                    user_id=current_user.id,
                    user_client_id=current_user.client_id,
                    requested_client_id=client_id
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: insufficient permissions for this client"
                )
            return current_user
        
        # Affiliate users have no client access by default
        logger.warning(
            "Access denied: affiliates cannot access client data",
            user_id=current_user.id,
            user_role=current_user.role
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: affiliates cannot access client data"
        )
    
    return client_access_dependency

def get_submission_user(
    request: Request,
    db: Session = Depends(get_db),
    x_discord_user_id: str | None = Header(None, alias="X-Discord-User-ID"),
) -> User:
    """Hybrid auth for submission endpoints.

    Allows either:
      1. Standard user Bearer API key (same as get_current_user)
      2. Bot internal token (Authorization: Bot <token>) + X-Discord-User-ID header
         which maps to an active affiliate user by discord_user_id.

    This narrows bot privileges to submission actions while keeping existing
    API key flow intact for direct user API usage.
    """
    from app.config import BOT_INTERNAL_TOKEN

    # Get authorization header
    auth_header = request.headers.get("Authorization", "")
    
    # Path 1: Standard user API key flow
    if auth_header.startswith("Bearer "):
        api_key = auth_header[7:]  # Remove "Bearer " prefix
        
        user = db.query(User).filter(
            User.api_key == api_key,
            User.is_active == True
        ).first()
        
        if user:
            logger.info(
                "User authenticated via API key for submission",
                user_id=user.id,
                user_name=user.name,
                user_role=user.role
            )
            return user
    
    # Path 2: Bot token flow (only for affiliate users)
    elif auth_header.startswith("Bot "):
        bot_token = auth_header[4:]  # Remove "Bot " prefix
        
        if bot_token != BOT_INTERNAL_TOKEN:
            logger.warning(
                "Bot authentication failed: invalid token",
                provided_token_prefix=bot_token[:10] + "..." if len(bot_token) > 10 else bot_token
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bot token"
            )
        
        if not x_discord_user_id:
            logger.warning("Bot authentication failed: missing Discord user ID header")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Discord-User-ID header required for bot authentication"
            )
        
        # Find affiliate user by Discord ID
        user = db.query(User).filter(
            User.discord_user_id == x_discord_user_id,
            User.role == UserRole.AFFILIATE,  # Only affiliate users can submit via bot
            User.is_active == True
        ).first()
        
        if not user:
            logger.warning(
                "Bot authentication failed: Discord user not found or not affiliate",
                discord_user_id=x_discord_user_id
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Active affiliate user with Discord ID '{x_discord_user_id}' not found"
            )
        
        logger.info(
            "User authenticated via bot token for submission",
            user_id=user.id,
            user_name=user.name,
            discord_user_id=x_discord_user_id
        )
        
        return user
    
    # No valid authentication found
    logger.warning("Submission authentication failed: no valid credentials")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Valid authentication required (Bearer token or Bot token with Discord ID)",
        headers={"WWW-Authenticate": "Bearer"}
    )

# Legacy alias for backward compatibility
get_submission_affiliate = get_submission_user

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

def get_campaign_if_authorized(
    campaign_id: int,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.CLIENT])),
    db: Session = Depends(get_db)
) -> Campaign:
    """Fetch a campaign and enforce RBAC access rules.

    Access rules:
      * ADMIN: any campaign
      * CLIENT: only campaigns whose client_id matches the user's client_id
      * AFFILIATE: filtered out by require_role dependency

    Returns the campaign object if authorized.
    Raises 404 if campaign not found, 403 if client mismatch.
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        logger.warning(
            "Campaign not found during access check", campaign_id=campaign_id
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found"
        )
    if current_user.role == UserRole.CLIENT and current_user.client_id != campaign.client_id:
        logger.warning(
            "Client access denied for campaign",
            user_id=current_user.id,
            campaign_id=campaign_id,
            user_client_id=current_user.client_id,
            campaign_client_id=campaign.client_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )
    return campaign

