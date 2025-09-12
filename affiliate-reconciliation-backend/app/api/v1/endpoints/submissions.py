"""
Affiliate submission endpoints with comprehensive audit logging.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request, Query
from sqlalchemy.orm import Session
import time
from app.api.deps import get_db, get_current_affiliate, validate_campaign_exists, validate_platform_exists
from app.models.db import Post, AffiliateReport, Affiliate, Campaign, Platform
from app.models.schemas.affiliates import AffiliatePostSubmission
from app.models.schemas.posts import PostRead
from app.models.schemas.base import ResponseBase
from app.utils import get_logger, log_business_event, log_performance

router = APIRouter()
logger = get_logger(__name__)

@router.post(
    "/",
    response_model=ResponseBase,
    status_code=status.HTTP_201_CREATED,
    summary="Submit affiliate post"
)
async def submit_post(
    submission: AffiliatePostSubmission,
    background_tasks: BackgroundTasks,
    request: Request,
    current_affiliate: Affiliate = Depends(get_current_affiliate),
    db: Session = Depends(get_db)
) -> ResponseBase:
    """Submit a new post with claimed metrics."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Post submission started",
        affiliate_id=current_affiliate.id,
        affiliate_name=current_affiliate.name,
        campaign_id=submission.campaign_id,
        platform_id=submission.platform_id,
        post_url=submission.post_url,
        submission_method=submission.submission_method.value,
        claimed_metrics={
            "views": submission.claimed_views,
            "clicks": submission.claimed_clicks,
            "conversions": submission.claimed_conversions
        },
        request_id=request_id
    )
    
    try:
        # Validate campaign and platform
        campaign = db.query(Campaign).filter(
            Campaign.id == submission.campaign_id,
            Campaign.status == "active"
        ).first()
        
        if not campaign:
            logger.warning(
                "Post submission failed: invalid campaign",
                affiliate_id=current_affiliate.id,
                campaign_id=submission.campaign_id,
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign with id {submission.campaign_id} not found or not active"
            )
        
        platform = db.query(Platform).filter(
            Platform.id == submission.platform_id,
            Platform.is_active == True
        ).first()
        
        if not platform:
            logger.warning(
                "Post submission failed: invalid platform",
                affiliate_id=current_affiliate.id,
                platform_id=submission.platform_id,
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Platform with id {submission.platform_id} not found or inactive"
            )
        
        # Validate campaign-platform relationship
        if platform not in campaign.platforms:
            logger.warning(
                "Post submission failed: platform not in campaign",
                affiliate_id=current_affiliate.id,
                campaign_id=campaign.id,
                platform_id=platform.id,
                campaign_name=campaign.name,
                platform_name=platform.name,
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Platform '{platform.name}' is not assigned to campaign '{campaign.name}'"
            )
        
        # Check for duplicates
        existing_post = db.query(Post).filter(
            Post.campaign_id == submission.campaign_id,
            Post.platform_id == submission.platform_id,
            Post.url == submission.post_url,
            Post.affiliate_id == current_affiliate.id
        ).first()
        
        if existing_post:
            logger.warning(
                "Post submission failed: duplicate post",
                affiliate_id=current_affiliate.id,
                existing_post_id=existing_post.id,
                post_url=submission.post_url,
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already submitted this post for this campaign"
            )
        
        # Create Post and AffiliateReport
        post = Post(
            campaign_id=submission.campaign_id,
            affiliate_id=current_affiliate.id,
            platform_id=submission.platform_id,
            url=submission.post_url,
            title=submission.title,
            description=submission.description
        )
        db.add(post)
        db.flush()
        
        affiliate_report = AffiliateReport(
            post_id=post.id,
            claimed_views=submission.claimed_views,
            claimed_clicks=submission.claimed_clicks,
            claimed_conversions=submission.claimed_conversions,
            evidence_data=submission.evidence_data,
            submission_method=submission.submission_method,
            status="PENDING"
        )
        db.add(affiliate_report)
        
        # Update affiliate metrics
        current_affiliate.total_submissions += 1
        
        db.commit()
        db.refresh(post)
        db.refresh(affiliate_report)
        
        # Log business event
        log_business_event(
            event_type="affiliate_post_submitted",
            details={
                "post_id": post.id,
                "affiliate_report_id": affiliate_report.id,
                "campaign_name": campaign.name,
                "platform_name": platform.name,
                "post_url": submission.post_url,
                "claimed_metrics": {
                    "views": submission.claimed_views,
                    "clicks": submission.claimed_clicks,
                    "conversions": submission.claimed_conversions
                },
                "submission_method": submission.submission_method.value,
                "evidence_provided": bool(submission.evidence_data)
            },
            user_id=current_affiliate.id,
            request_id=request_id
        )
        
        # Queue reconciliation job (placeholder for now)
        logger.info(
            "Reconciliation job queued",
            affiliate_report_id=affiliate_report.id,
            post_id=post.id,
            request_id=request_id
        )
        
        # Log performance
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="submit_post",
            duration_ms=duration_ms,
            additional_data={
                "affiliate_id": current_affiliate.id,
                "campaign_id": campaign.id,
                "has_evidence": bool(submission.evidence_data)
            }
        )
        
        logger.info(
            "Post submission completed successfully",
            post_id=post.id,
            affiliate_report_id=affiliate_report.id,
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        return ResponseBase(
            success=True,
            message="Post submitted successfully. Reconciliation job queued.",
            data={
                "post_id": post.id,
                "affiliate_report_id": affiliate_report.id,
                "estimated_processing_time": "2-5 minutes"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Post submission failed with unexpected error",
            affiliate_id=current_affiliate.id,
            post_url=submission.post_url,
            error=str(e),
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during post submission"
        )

@router.get(
    "/history",
    response_model=List[PostRead],
    summary="Get submission history"
)
async def get_submission_history(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    campaign_id: Optional[int] = Query(None),
    platform_id: Optional[int] = Query(None),
    current_affiliate: Affiliate = Depends(get_current_affiliate),
    db: Session = Depends(get_db)
) -> List[PostRead]:
    """Get submission history for the authenticated affiliate."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Submission history requested",
        affiliate_id=current_affiliate.id,
        limit=limit,
        offset=offset,
        campaign_filter=campaign_id,
        platform_filter=platform_id,
        request_id=request_id
    )
    
    try:
        query = db.query(Post).filter(Post.affiliate_id == current_affiliate.id)
        
        if campaign_id:
            query = query.filter(Post.campaign_id == campaign_id)
        
        if platform_id:
            query = query.filter(Post.platform_id == platform_id)
        
        posts = query.order_by(Post.created_at.desc()).offset(offset).limit(limit).all()
        
        # Log performance
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="get_submission_history",
            duration_ms=duration_ms,
            additional_data={
                "affiliate_id": current_affiliate.id,
                "posts_returned": len(posts)
            }
        )
        
        logger.info(
            "Submission history completed",
            affiliate_id=current_affiliate.id,
            posts_returned=len(posts),
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        return [PostRead.from_orm(post) for post in posts]
        
    except Exception as e:
        logger.error(
            "Submission history failed",
            affiliate_id=current_affiliate.id,
            error=str(e),
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving submission history"
        )
