"""
Reconciliation management endpoints.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, selectinload
import time
from app.api.deps import get_db
from app.models.db import ReconciliationLog, AffiliateReport, PlatformReport
from app.models.schemas.reconciliation import ReconciliationResult, ReconciliationTrigger
from app.models.schemas.base import ResponseBase
from app.utils import get_logger, log_business_event, log_performance

router = APIRouter()
logger = get_logger(__name__)

@router.post(
    "/run",
    response_model=ResponseBase,
    summary="Trigger reconciliation manually"
)
async def trigger_reconciliation(
    trigger_data: ReconciliationTrigger,
    request: Request,
    db: Session = Depends(get_db)
) -> ResponseBase:
    """Manually trigger reconciliation for specific posts or all pending."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Manual reconciliation triggered",
        post_id=trigger_data.post_id,
        force_reprocess=trigger_data.force_reprocess,
        request_id=request_id
    )
    
    try:
        # TODO: Implement actual reconciliation logic
        # For now, return mock response
        
        if trigger_data.post_id:
            message = f"Reconciliation queued for post {trigger_data.post_id}"
            posts_count = 1
        else:
            message = "Reconciliation queued for all pending posts"
            posts_count = db.query(AffiliateReport).filter(
                AffiliateReport.status == "PENDING"
            ).count()
        
        # Log business event
        log_business_event(
            event_type="manual_reconciliation_triggered",
            details={
                "post_id": trigger_data.post_id,
                "force_reprocess": trigger_data.force_reprocess,
                "estimated_posts": posts_count
            },
            request_id=request_id
        )
        
        # Log performance
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="trigger_reconciliation",
            duration_ms=duration_ms,
            additional_data={"posts_to_process": posts_count}
        )
        
        logger.info(
            "Reconciliation trigger completed",
            posts_queued=posts_count,
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        return ResponseBase(
            success=True,
            message=message,
            data={
                "posts_queued": posts_count,
                "estimated_completion": f"{posts_count * 2}-{posts_count * 5} minutes"
            }
        )
        
    except Exception as e:
        logger.error(
            "Reconciliation trigger failed",
            error=str(e),
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during reconciliation trigger"
        )

@router.get(
    "/results",
    response_model=List[Dict[str, Any]],
    summary="Get reconciliation results"
)
async def get_reconciliation_results(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None),
    discrepancy_level: Optional[str] = Query(None),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get reconciliation results with filtering and pagination."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Reconciliation results requested",
        limit=limit,
        offset=offset,
        status_filter=status_filter,
        discrepancy_level=discrepancy_level,
        request_id=request_id
    )
    
    try:
        query = db.query(ReconciliationLog).options(
            selectinload(ReconciliationLog.affiliate_report),
            selectinload(ReconciliationLog.platform_report)
        )
        
        if status_filter:
            query = query.filter(ReconciliationLog.status == status_filter)
        
        if discrepancy_level:
            query = query.filter(ReconciliationLog.discrepancy_level == discrepancy_level)
        
        results = query.order_by(ReconciliationLog.processed_at.desc()).offset(offset).limit(limit).all()
        
        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append({
                "id": result.id,
                "affiliate_report_id": result.affiliate_report_id,
                "platform_report_id": result.platform_report_id,
                "status": result.status,
                "discrepancy_level": result.discrepancy_level,
                "views_discrepancy": result.views_discrepancy,
                "clicks_discrepancy": result.clicks_discrepancy,
                "conversions_discrepancy": result.conversions_discrepancy,
                "views_diff_pct": float(result.views_diff_pct) if result.views_diff_pct is not None else None,
                "clicks_diff_pct": float(result.clicks_diff_pct) if result.clicks_diff_pct is not None else None,
                "conversions_diff_pct": float(result.conversions_diff_pct) if result.conversions_diff_pct is not None else None,
                "processed_at": result.processed_at,
                "notes": result.notes
            })
        
        # Log performance
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="get_reconciliation_results",
            duration_ms=duration_ms,
            additional_data={"results_returned": len(formatted_results)}
        )
        
        logger.info(
            "Reconciliation results completed",
            results_returned=len(formatted_results),
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        return formatted_results
        
    except Exception as e:
        logger.error(
            "Reconciliation results failed",
            error=str(e),
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving reconciliation results"
        )

