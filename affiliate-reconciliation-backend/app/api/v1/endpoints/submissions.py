"""
Affiliate submission endpoints with comprehensive audit logging.
Integrates link processing and validation for URL cleaning and platform detection.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request, Query
from sqlalchemy.orm import Session
import time
from app.api.deps import get_db, get_current_affiliate
from app.models.db import Post, AffiliateReport, Affiliate, Campaign, Platform
from app.models.schemas.affiliates import AffiliatePostSubmission
from app.models.schemas.posts import PostRead
from app.models.schemas.base import ResponseBase
from app.utils import get_logger, log_business_event, log_performance, process_post_url

router = APIRouter()
logger = get_logger(__name__)

@router.post(
    "/",
    response_model=ResponseBase,
    status_code=status.HTTP_201_CREATED,
    summary="Submit new affiliate post",
    description="Create a new post submission with initial metrics"
)
async def submit_post(
    submission: AffiliatePostSubmission,
    background_tasks: BackgroundTasks,
    request: Request,
    current_affiliate: Affiliate = Depends(get_current_affiliate),
    db: Session = Depends(get_db)
) -> ResponseBase:
    """Submit a brand new post with claimed metrics."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "New post submission started",
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
        
        # CRITICAL: Process URL with full validation pipeline
        try:
            processed_url, detected_platform = await process_post_url(
                submission.post_url, 
                platform.name
            )
            
            logger.info(
                "URL processing completed successfully",
                affiliate_id=current_affiliate.id,
                original_url=submission.post_url,
                processed_url=processed_url,
                detected_platform=detected_platform,
                expected_platform=platform.name,
                url_changed=submission.post_url != processed_url,
                request_id=request_id
            )
            
        except ValueError as e:
            logger.warning(
                "Post submission failed: URL processing error",
                affiliate_id=current_affiliate.id,
                post_url=submission.post_url,
                platform_name=platform.name,
                error=str(e),
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"URL processing failed: {str(e)}"
            )
        
        # Check if post already exists with processed URL - should FAIL for POST
        existing_post = db.query(Post).filter(
            Post.campaign_id == submission.campaign_id,
            Post.platform_id == submission.platform_id,
            Post.url == processed_url,  # Use processed URL for duplicate check
            Post.affiliate_id == current_affiliate.id
        ).first()
        
        if existing_post:
            logger.warning(
                "Post submission failed: post already exists",
                affiliate_id=current_affiliate.id,
                existing_post_id=existing_post.id,
                processed_url=processed_url,
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Post already exists with id {existing_post.id}. Use PUT /submissions/{existing_post.id}/metrics to update metrics."
            )
        
        # Create NEW post with processed URL
        post = Post(
            campaign_id=submission.campaign_id,
            affiliate_id=current_affiliate.id,
            platform_id=submission.platform_id,
            url=processed_url,  # Store the clean, processed URL
            title=submission.title,
            description=submission.description
        )
        db.add(post)
        db.flush()  # Assign post.id
        
        # Create first affiliate report
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
        
        # Update affiliate metrics for new post
        current_affiliate.total_submissions += 1
        
        db.commit()
        db.refresh(post)
        db.refresh(affiliate_report)
        
        # Log business event
        log_business_event(
            event_type="affiliate_post_created",
            details={
                "post_id": post.id,
                "affiliate_report_id": affiliate_report.id,
                "campaign_name": campaign.name,
                "platform_name": platform.name,
                "original_url": submission.post_url,
                "processed_url": processed_url,
                "url_changed": submission.post_url != processed_url,
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
        
        # Queue reconciliation job for this affiliate report
        # TODO: Replace with actual job queue implementation
        logger.info(
            "Reconciliation job queued for new post",
            affiliate_report_id=affiliate_report.id,
            post_id=post.id,
            request_id=request_id
        )
        
        # Log performance
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="submit_new_post",
            duration_ms=duration_ms,
            additional_data={
                "affiliate_id": current_affiliate.id,
                "campaign_id": campaign.id,
                "has_evidence": bool(submission.evidence_data),
                "url_processing_required": submission.post_url != processed_url
            }
        )
        
        logger.info(
            "New post submission completed successfully",
            post_id=post.id,
            affiliate_report_id=affiliate_report.id,
            processed_url=processed_url,
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        return ResponseBase(
            success=True,
            message="Post submitted successfully. Reconciliation job queued.",
            data={
                "post_id": post.id,
                "affiliate_report_id": affiliate_report.id,
                "processed_url": processed_url,
                "url_was_modified": submission.post_url != processed_url,
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
            detail="Failed to submit new post"
        )

@router.put(
    "/{post_id}/metrics",
    response_model=ResponseBase,
    summary="Update post metrics",
    description="Submit updated metrics for an existing post"
)
async def update_post_metrics(
    post_id: int,
    submission: AffiliatePostSubmission,
    background_tasks: BackgroundTasks,
    request: Request,
    current_affiliate: Affiliate = Depends(get_current_affiliate),
    db: Session = Depends(get_db)
) -> ResponseBase:
    """Update metrics for an existing post (creates new AffiliateReport for historical tracking)."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Post metrics update started",
        affiliate_id=current_affiliate.id,
        post_id=post_id,
        claimed_metrics={
            "views": submission.claimed_views,
            "clicks": submission.claimed_clicks,
            "conversions": submission.claimed_conversions
        },
        request_id=request_id
    )
    
    try:
        # Get existing post
        post = db.query(Post).filter(
            Post.id == post_id,
            Post.affiliate_id == current_affiliate.id  # Security: only own posts
        ).first()
        
        if not post:
            logger.warning(
                "Post metrics update failed: post not found",
                affiliate_id=current_affiliate.id,
                post_id=post_id,
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Post with id {post_id} not found or you don't have permission to update it"
            )
        
        # Process the submitted URL to ensure consistency
        try:
            platform = db.query(Platform).filter(
                Platform.id == post.platform_id,
                Platform.is_active == True
            ).first()
            
            if not platform:
                logger.error(
                    "Post metrics update failed: platform not found",
                    affiliate_id=current_affiliate.id,
                    post_id=post_id,
                    platform_id=post.platform_id,
                    request_id=request_id
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Post references invalid platform"
                )
            
            processed_url, _ = await process_post_url(submission.post_url, platform.name)
            
            # Validate that processed URL matches existing post
            if processed_url != post.url:
                logger.warning(
                    "Post metrics update failed: URL mismatch after processing",
                    affiliate_id=current_affiliate.id,
                    post_id=post_id,
                    existing_url=post.url,
                    submitted_url=submission.post_url,
                    processed_url=processed_url,
                    request_id=request_id
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Submitted URL does not match existing post URL"
                )
        except ValueError as e:
            logger.warning(
                "Post metrics update failed: URL processing error",
                affiliate_id=current_affiliate.id,
                post_id=post_id,
                submitted_url=submission.post_url,
                error=str(e),
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"URL processing failed: {str(e)}"
            )
        
        # Validate the submission data matches the existing post
        if (submission.campaign_id != post.campaign_id or 
            submission.platform_id != post.platform_id):
            logger.warning(
                "Post metrics update failed: data mismatch",
                affiliate_id=current_affiliate.id,
                post_id=post_id,
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Campaign ID and platform ID must match the existing post"
            )
        
        # Update post metadata if provided
        if submission.title and submission.title != post.title:
            post.title = submission.title
        if submission.description and submission.description != post.description:
            post.description = submission.description
        
        # Create new affiliate report for updated metrics
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
        
        db.commit()
        db.refresh(affiliate_report)
        
        # Log business event
        log_business_event(
            event_type="affiliate_post_metrics_updated",
            details={
                "post_id": post.id,
                "affiliate_report_id": affiliate_report.id,
                "updated_metrics": {
                    "views": submission.claimed_views,
                    "clicks": submission.claimed_clicks,
                    "conversions": submission.claimed_conversions
                },
                "submission_method": submission.submission_method.value,
                "evidence_provided": bool(submission.evidence_data),
                "total_reports_for_post": len(post.affiliate_reports)
            },
            user_id=current_affiliate.id,
            request_id=request_id
        )
        
        # Queue reconciliation job for this updated report
        logger.info(
            "Reconciliation job queued for updated metrics",
            affiliate_report_id=affiliate_report.id,
            post_id=post.id,
            request_id=request_id
        )
        
        # Log performance
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="update_post_metrics",
            duration_ms=duration_ms,
            additional_data={
                "affiliate_id": current_affiliate.id,
                "post_id": post.id,
                "has_evidence": bool(submission.evidence_data)
            }
        )
        
        logger.info(
            "Post metrics update completed successfully",
            post_id=post.id,
            affiliate_report_id=affiliate_report.id,
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        return ResponseBase(
            success=True,
            message="Post metrics updated successfully. Reconciliation job queued.",
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
            "Post metrics update failed with unexpected error",
            affiliate_id=current_affiliate.id,
            post_id=post_id,
            error=str(e),
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update post metrics"
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
        
        return [PostRead.model_validate(post) for post in posts]
        
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
            detail="Failed to retrieve submission history"
        )

@router.get(
    "/{post_id}/metrics",
    response_model=List[dict],  # Will contain affiliate reports with timestamps
    summary="Get post metrics history"
)
async def get_post_metrics_history(
    post_id: int,
    request: Request,
    current_affiliate: Affiliate = Depends(get_current_affiliate),
    db: Session = Depends(get_db)
) -> List[dict]:
    """Get all metrics reports for a specific post (historical tracking)."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Post metrics history requested",
        affiliate_id=current_affiliate.id,
        post_id=post_id,
        request_id=request_id
    )
    
    try:
        # Get post and verify ownership
        post = db.query(Post).filter(
            Post.id == post_id,
            Post.affiliate_id == current_affiliate.id
        ).first()
        
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Post with id {post_id} not found or you don't have permission to view it"
            )
        
        # Get all affiliate reports for this post, ordered by submission time
        reports = db.query(AffiliateReport).filter(
            AffiliateReport.post_id == post_id
        ).order_by(AffiliateReport.submitted_at.asc()).all()
        
        metrics_history = []
        for report in reports:
            metrics_history.append({
                "affiliate_report_id": report.id,
                "claimed_views": report.claimed_views,
                "claimed_clicks": report.claimed_clicks,
                "claimed_conversions": report.claimed_conversions,
                "submission_method": report.submission_method,
                "status": report.status,
                "submitted_at": report.submitted_at,
                "evidence_provided": bool(report.evidence_data)
            })
        
        # Log performance
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="get_post_metrics_history",
            duration_ms=duration_ms,
            additional_data={
                "affiliate_id": current_affiliate.id,
                "post_id": post_id,
                "reports_returned": len(metrics_history)
            }
        )
        
        logger.info(
            "Post metrics history completed",
            affiliate_id=current_affiliate.id,
            post_id=post_id,
            reports_returned=len(metrics_history),
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        return metrics_history
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Post metrics history failed",
            affiliate_id=current_affiliate.id,
            post_id=post_id,
            error=str(e),
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve post metrics history"
        )