"""
Campaign management endpoints with comprehensive logging.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, selectinload
import time
from app.api.deps import get_db, validate_platform_exists
from app.models.db import Campaign, Platform
from app.models.schemas.campaigns import CampaignCreate, CampaignRead, CampaignUpdate
from app.models.schemas.base import ResponseBase
from app.utils import get_logger, log_business_event, log_performance

router = APIRouter()
logger = get_logger(__name__)

@router.post(
    "/",
    response_model=CampaignRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create new campaign",
    description="Create a new advertising campaign with assigned platforms"
)
async def create_campaign(
    campaign_data: CampaignCreate,
    request: Request,
    db: Session = Depends(get_db)
) -> CampaignRead:
    """Create a new campaign with platform assignments."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Campaign creation started",
        campaign_name=campaign_data.name,
        advertiser=campaign_data.advertiser_name,
        platform_count=len(campaign_data.platform_ids),
        request_id=request_id
    )
    
    try:
        # Check for duplicate campaign name
        existing = db.query(Campaign).filter(Campaign.name == campaign_data.name).first()
        if existing:
            logger.warning(
                "Campaign creation failed: duplicate name",
                campaign_name=campaign_data.name,
                existing_campaign_id=existing.id,
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Campaign with name '{campaign_data.name}' already exists"
            )
        
        # Validate platform IDs
        platforms = db.query(Platform).filter(
            Platform.id.in_(campaign_data.platform_ids),
            Platform.is_active == True
        ).all()
        
        if len(platforms) != len(campaign_data.platform_ids):
            found_ids = {p.id for p in platforms}
            missing_ids = set(campaign_data.platform_ids) - found_ids
            logger.error(
                "Campaign creation failed: invalid platforms",
                campaign_name=campaign_data.name,
                missing_platform_ids=list(missing_ids),
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or inactive platform IDs: {list(missing_ids)}"
            )
        
        # Create campaign
        campaign_dict = campaign_data.dict(exclude={"platform_ids"})
        campaign = Campaign(**campaign_dict)
        campaign.platforms = platforms
        
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        
        # Log business event
        log_business_event(
            event_type="campaign_created",
            details={
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "advertiser_name": campaign.advertiser_name,
                "platform_ids": campaign_data.platform_ids,
                "platform_names": [p.name for p in platforms]
            },
            request_id=request_id
        )
        
        # Log performance
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="create_campaign",
            duration_ms=duration_ms,
            additional_data={
                "campaign_id": campaign.id,
                "platform_count": len(platforms)
            }
        )
        
        logger.info(
            "Campaign created successfully",
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        return CampaignRead.from_orm(campaign)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Campaign creation failed with unexpected error",
            campaign_name=campaign_data.name,
            error=str(e),
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during campaign creation"
        )

@router.get(
    "/",
    response_model=List[CampaignRead],
    summary="List campaigns"
)
async def list_campaigns(
    request: Request,
    status_filter: Optional[str] = Query(None, regex="^(active|paused|ended)$"),
    advertiser: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
) -> List[CampaignRead]:
    """List campaigns with filtering and pagination."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Campaign list requested",
        status_filter=status_filter,
        advertiser_filter=advertiser,
        limit=limit,
        offset=offset,
        request_id=request_id
    )
    
    try:
        query = db.query(Campaign)
        
        if status_filter:
            query = query.filter(Campaign.status == status_filter)
        
        if advertiser:
            query = query.filter(Campaign.advertiser_name.ilike(f"%{advertiser}%"))
        
        campaigns = query.offset(offset).limit(limit).all()
        
        # Log performance
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="list_campaigns",
            duration_ms=duration_ms,
            additional_data={
                "campaigns_returned": len(campaigns),
                "filters_applied": bool(status_filter or advertiser)
            }
        )
        
        logger.info(
            "Campaign list completed",
            campaigns_returned=len(campaigns),
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        return [CampaignRead.from_orm(campaign) for campaign in campaigns]
        
    except Exception as e:
        logger.error(
            "Campaign list failed",
            error=str(e),
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while listing campaigns"
        )