"""
Affiliate management endpoints.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
import time
from app.api.deps import get_db, get_current_affiliate
from sqlalchemy.exc import IntegrityError
from app.models.db import Affiliate
from app.models.schemas.affiliates import AffiliateCreate, AffiliateRead, AffiliateUpdate
from app.models.schemas.base import ResponseBase
from app.utils import get_logger, log_business_event, log_performance

router = APIRouter()
logger = get_logger(__name__)

@router.post(
    "/",
    response_model=AffiliateRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create new affiliate",
    description="Register a new affiliate partner"
)
async def create_affiliate(
    affiliate_data: AffiliateCreate,
    request: Request,
    db: Session = Depends(get_db)
) -> AffiliateRead:
    """Create a new affiliate partner."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Affiliate creation started",
        affiliate_name=affiliate_data.name,
        affiliate_email=affiliate_data.email,
        has_discord=bool(affiliate_data.discord_user_id),
        request_id=request_id
    )
    
    try:
        existing_email = db.query(Affiliate).filter(Affiliate.email == affiliate_data.email).first()
        if existing_email:
            logger.warning(
                "Affiliate creation failed: duplicate email (pre-check)",
                email=affiliate_data.email,
                existing_affiliate_id=existing_email.id,
                request_id=request_id
            )
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        import secrets
        api_key = f"aff_{secrets.token_urlsafe(32)}"
        affiliate = Affiliate(**affiliate_data.model_dump(), api_key=api_key)
        db.add(affiliate)
        db.commit()
        db.refresh(affiliate)
        
        # Log business event
        log_business_event(
            event_type="affiliate_created",
            details={
                "affiliate_id": affiliate.id,
                "affiliate_name": affiliate.name,
                "affiliate_email": affiliate.email,
                "has_discord_id": bool(affiliate.discord_user_id),
                "api_key_generated": True
            },
            user_id=affiliate.id,
            request_id=request_id
        )
        
        # Log performance
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="create_affiliate",
            duration_ms=duration_ms,
            additional_data={"affiliate_id": affiliate.id}
        )
        
        logger.info(
            "Affiliate created successfully",
            affiliate_id=affiliate.id,
            affiliate_name=affiliate.name,
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        return AffiliateRead.model_validate(affiliate)
        
    except IntegrityError as ie:
        db.rollback()
        # Determine which unique constraint failed (simplistic message parsing)
        msg = str(ie.orig).lower()
        conflict_field = "email" if "email" in msg else ("name" if "name" in msg else "unique field")
        logger.warning(
            "Affiliate creation integrity error",
            conflict_field=conflict_field,
            error=str(ie),
            request_id=request_id
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Affiliate with that {conflict_field} already exists")
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(
            "Affiliate creation failed with unexpected error",
            affiliate_name=affiliate_data.name,
            error=str(e),
            request_id=request_id,
            exc_info=True
        )
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during affiliate creation")

@router.get(
    "/me",
    response_model=AffiliateRead,
    summary="Get current affiliate profile"
)
async def get_current_affiliate_profile(
    request: Request,
    current_affiliate: Affiliate = Depends(get_current_affiliate)
) -> AffiliateRead:
    """Get the current authenticated affiliate's profile."""
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Affiliate profile requested",
        affiliate_id=current_affiliate.id,
        request_id=request_id
    )
    
    return AffiliateRead.model_validate(current_affiliate)

@router.put(
    "/me",
    response_model=AffiliateRead,
    summary="Update current affiliate profile"
)
async def update_current_affiliate(
    update_data: AffiliateUpdate,
    request: Request,
    current_affiliate: Affiliate = Depends(get_current_affiliate),
    db: Session = Depends(get_db)
) -> AffiliateRead:
    """Update the current authenticated affiliate's profile."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Affiliate profile update started",
        affiliate_id=current_affiliate.id,
        update_fields=list(update_data.model_dump(exclude_unset=True).keys()),
        request_id=request_id
    )

    try:
        update_dict = update_data.model_dump(exclude_unset=True)
        
        # Check for email conflicts if email is being updated
        if "email" in update_dict:
            existing = db.query(Affiliate).filter(
                Affiliate.email == update_dict["email"],
                Affiliate.id != current_affiliate.id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Email '{update_dict['email']}' is already in use"
                )
        
        # Check for name conflicts if name is being updated
        if "name" in update_dict:
            existing = db.query(Affiliate).filter(
                Affiliate.name == update_dict["name"],
                Affiliate.id != current_affiliate.id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Name '{update_dict['name']}' is already in use"
                )
        
        for field, value in update_dict.items():
            setattr(current_affiliate, field, value)
        
        db.commit()
        db.refresh(current_affiliate)
        
        # Log business event
        log_business_event(
            event_type="affiliate_profile_updated",
            details={
                "affiliate_id": current_affiliate.id,
                "updated_fields": list(update_dict.keys()),
                "new_values": {k: v for k, v in update_dict.items() if k != "email"}  # Don't log sensitive data
            },
            user_id=current_affiliate.id,
            request_id=request_id
        )
        
        # Log performance
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="update_affiliate_profile",
            duration_ms=duration_ms,
            additional_data={"affiliate_id": current_affiliate.id}
        )
        
        return AffiliateRead.model_validate(current_affiliate)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Affiliate profile update failed",
            affiliate_id=current_affiliate.id,
            error=str(e),
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during profile update"
        )

