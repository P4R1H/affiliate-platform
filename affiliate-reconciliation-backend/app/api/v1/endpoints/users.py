"""
User management endpoints (includes affiliates and clients).
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, selectinload
import time
from app.api.deps import get_db, require_admin  # Note: will need to update get_current_affiliate to get_current_user
from sqlalchemy.exc import IntegrityError
from app.models.db import User, Client
from app.models.db.enums import UserRole
from app.models.schemas.users import (
    UserCreate, UserRead, UserUpdate, UserCreateAffiliate, UserCreateClient
)
from app.models.schemas.base import ResponseBase
from app.utils import get_logger, log_business_event, log_performance
import secrets
import string

router = APIRouter()
logger = get_logger(__name__)

def generate_api_key() -> str:
    """Generate a secure API key."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(32))

@router.post(
    "/",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create new user",
    description="Register a new user (affiliate or client based on role)"
)
async def create_user(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db)
) -> UserRead:
    """Create a new user (affiliate, client, or admin)."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "User creation started",
        user_name=user_data.name,
        user_email=user_data.email,
        user_role=user_data.role.value,
        has_discord=bool(user_data.discord_user_id),
        client_id=user_data.client_id,
        request_id=request_id
    )
    
    try:
        # For CLIENT role users, verify client exists
        if user_data.role == UserRole.CLIENT and user_data.client_id:
            client = db.query(Client).filter(Client.id == user_data.client_id).first()
            if not client:
                logger.warning(
                    "User creation failed: client not found",
                    client_id=user_data.client_id,
                    request_id=request_id
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Client with ID {user_data.client_id} not found"
                )
        
        # Check for duplicate email
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            logger.warning(
                "User creation failed: duplicate email",
                email=user_data.email,
                existing_user_id=existing_email.id,
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email '{user_data.email}' already exists"
            )
        
        # Generate API key
        api_key = generate_api_key()
        
        # Create new user with role-specific defaults
        new_user = User(
            name=user_data.name,
            email=user_data.email,
            discord_user_id=user_data.discord_user_id,
            api_key=api_key,
            role=user_data.role,
            client_id=user_data.client_id,
            trust_score=0.50 if user_data.role == UserRole.AFFILIATE else None  # Trust score only for affiliates
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        log_business_event(
            event_type="user_created",
            details={
                "user_name": new_user.name,
                "user_email": new_user.email,
                "user_role": new_user.role.value,
                "client_id": new_user.client_id,
                "has_discord_id": bool(new_user.discord_user_id),
                "api_key_generated": True
            },
            user_id=new_user.id,
            request_id=request_id
        )
        
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="create_user",
            duration_ms=duration_ms,
            additional_data={"user_id": new_user.id, "role": new_user.role.value}
        )
        
        logger.info(
            "User created successfully",
            user_id=new_user.id,
            user_name=new_user.name,
            user_role=new_user.role.value,
            request_id=request_id
        )
        
        return UserRead.model_validate(new_user)
        
    except HTTPException:
        raise
    except IntegrityError as e:
        logger.error(
            "User creation failed: database integrity error",
            error=str(e),
            user_name=user_data.name,
            user_email=user_data.email,
            user_role=user_data.role.value,
            request_id=request_id
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email or name already exists"
        )
    except Exception as e:
        logger.error(
            "User creation failed with unexpected error",
            error=str(e),
            user_name=user_data.name,
            user_role=user_data.role.value,
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )

@router.post(
    "/clients",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create new client user",
    description="Register a new client user (admin only)"
)
async def create_client_user(
    user_data: UserCreateClient,
    request: Request,
    admin=Depends(require_admin),
    db: Session = Depends(get_db)
) -> UserRead:
    """Create a new client user."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Client user creation started",
        user_name=user_data.name,
        user_email=user_data.email,
        client_id=user_data.client_id,
        admin_id=admin.id,
        request_id=request_id
    )
    
    try:
        # Verify client exists
        client = db.query(Client).filter(Client.id == user_data.client_id).first()
        if not client:
            logger.warning(
                "Client user creation failed: client not found",
                client_id=user_data.client_id,
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client with ID {user_data.client_id} not found"
            )
        
        # Check for duplicate email
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            logger.warning(
                "Client user creation failed: duplicate email",
                email=user_data.email,
                existing_user_id=existing_email.id,
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email '{user_data.email}' already exists"
            )
        
        # Generate API key
        api_key = generate_api_key()
        
        # Create new client user
        new_user = User(
            name=user_data.name,
            email=user_data.email,
            api_key=api_key,
            role=UserRole.CLIENT,
            client_id=user_data.client_id
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        log_business_event(
            event_type="client_user_created",
            details={
                "user_id": new_user.id,
                "user_name": new_user.name,
                "user_email": new_user.email,
                "client_id": new_user.client_id,
                "created_by_admin_id": admin.id,
                "api_key_generated": True
            },
            user_id=admin.id,
            request_id=request_id
        )
        
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="create_client_user",
            duration_ms=duration_ms,
            additional_data={"user_id": new_user.id, "client_id": user_data.client_id}
        )
        
        logger.info(
            "Client user created successfully",
            user_id=new_user.id,
            user_name=new_user.name,
            client_id=new_user.client_id,
            request_id=request_id
        )
        
        return UserRead.model_validate(new_user)
        
    except HTTPException:
        raise
    except IntegrityError as e:
        logger.error(
            "Client user creation failed: database integrity error",
            error=str(e),
            user_name=user_data.name,
            user_email=user_data.email,
            client_id=user_data.client_id,
            request_id=request_id
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email or name already exists"
        )
    except Exception as e:
        logger.error(
            "Client user creation failed with unexpected error",
            error=str(e),
            user_name=user_data.name,
            client_id=user_data.client_id,
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create client user"
        )

@router.get(
    "/",
    response_model=List[UserRead],
    summary="List users",
    description="Get list of users with optional role filtering (admin only)"
)
async def list_users(
    request: Request,
    admin=Depends(require_admin),
    role: Optional[UserRole] = Query(None, description="Filter by user role"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
) -> List[UserRead]:
    """Get list of users with optional role filtering."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "User list request started",
        admin_id=admin.id,
        role_filter=role,
        skip=skip,
        limit=limit,
        request_id=request_id
    )
    
    try:
        query = db.query(User)
        
        if role:
            query = query.filter(User.role == role)
        
        users = query.offset(skip).limit(limit).all()
        
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="list_users",
            duration_ms=duration_ms,
            additional_data={"user_count": len(users), "role_filter": role}
        )
        
        logger.info(
            "User list retrieved successfully",
            user_count=len(users),
            role_filter=role,
            request_id=request_id
        )
        
        return [UserRead.model_validate(user) for user in users]
        
    except Exception as e:
        logger.error(
            "User list retrieval failed",
            error=str(e),
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )