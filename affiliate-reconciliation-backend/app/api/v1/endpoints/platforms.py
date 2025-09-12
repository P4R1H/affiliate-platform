"""
Platform management endpoints.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import time
from app.api.deps import get_db
from app.models.db import Platform
from app.models.schemas.platform import PlatformAPIResponse
from app.models.schemas.base import ResponseBase
from app.utils import get_logger, log_business_event, log_performance

router = APIRouter()
logger = get_logger(__name__)

@router.get(
    "/",
    response_model=List[Dict[str, Any]],
    summary="List available platforms"
)
async def list_platforms(
    request: Request,
    active_only: bool = True,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """List all available advertising platforms."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Platform list requested",
        active_only=active_only,
        request_id=request_id
    )
    
    try:
        query = db.query(Platform)
        if active_only:
            query = query.filter(Platform.is_active == True)
        
        platforms = query.all()
        
        result = []
        for platform in platforms:
            result.append({
                "id": platform.id,
                "name": platform.name,
                "is_active": platform.is_active,
                "api_base_url": platform.api_base_url,
                "created_at": platform.created_at
            })
        
        # Log performance
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="list_platforms",
            duration_ms=duration_ms,
            additional_data={"platforms_returned": len(result)}
        )
        
        logger.info(
            "Platform list completed",
            platforms_returned=len(result),
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "Platform list failed",
            error=str(e),
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while listing platforms"
        )

@router.post(
    "/{platform_id}/fetch",
    response_model=ResponseBase,
    summary="Manually fetch platform data"
)
async def fetch_platform_data(
    platform_id: int,
    post_url: str,
    request: Request,
    db: Session = Depends(get_db)
) -> ResponseBase:
    """Manually trigger platform data fetch for a specific post."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Manual platform fetch requested",
        platform_id=platform_id,
        post_url=post_url,
        request_id=request_id
    )
    
    try:
        platform = db.query(Platform).filter(
            Platform.id == platform_id,
            Platform.is_active == True
        ).first()
        
        if not platform:
            logger.warning(
                "Platform fetch failed: platform not found",
                platform_id=platform_id,
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Platform with id {platform_id} not found or inactive"
            )
        
        # TODO: Implement actual platform integration
        # For now, return mock response
        logger.info(
            "Platform data fetch queued",
            platform_id=platform_id,
            platform_name=platform.name,
            post_url=post_url,
            request_id=request_id
        )
        
        # Log business event
        log_business_event(
            event_type="manual_platform_fetch_requested",
            details={
                "platform_id": platform_id,
                "platform_name": platform.name,
                "post_url": post_url
            },
            request_id=request_id
        )
        
        # Log performance
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="fetch_platform_data",
            duration_ms=duration_ms,
            additional_data={"platform_id": platform_id}
        )
        
        return ResponseBase(
            success=True,
            message=f"Platform data fetch queued for {platform.name}",
            data={
                "platform_id": platform_id,
                "platform_name": platform.name,
                "post_url": post_url,
                "estimated_completion": "2-5 minutes"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Platform fetch failed",
            platform_id=platform_id,
            error=str(e),
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during platform fetch"
        )

