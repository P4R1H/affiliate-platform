"""
Reconciliation management endpoints.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, selectinload
import time
from app.api.deps import get_db
from app.models.db import ReconciliationLog, AffiliateReport, PlatformReport, Post
from app.models.schemas.reconciliation import ReconciliationResult, ReconciliationTrigger
from app.models.schemas.base import ResponseBase
from app.utils import get_logger, log_business_event, log_performance
from app.services.trust_scoring import bucket_for_priority
from app.utils.priority import compute_priority
from app.jobs.reconciliation_job import ReconciliationJob

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
    """Manually enqueue reconciliation jobs.

    Modes:
      - post_id provided: enqueue latest affiliate report for that post (respect force_reprocess)
      - no post_id: enqueue all PENDING affiliate reports lacking a reconciliation_log (or all if force_reprocess)
    """
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")

    logger.info(
        "Manual reconciliation triggered",
        post_id=trigger_data.post_id,
        force_reprocess=trigger_data.force_reprocess,
        request_id=request_id
    )

    try:
        queue = getattr(request.app.state, "reconciliation_queue", None)  # type: ignore[attr-defined]
        if queue is None:
            raise HTTPException(status_code=503, detail="Reconciliation queue not available")

        enqueued: list[int] = []

        def enqueue_for_report(report: AffiliateReport):
            trust_score = float(getattr(report.post.affiliate, "trust_score", 0.5) or 0.5)
            bucket = bucket_for_priority(trust_score)
            priority_label = compute_priority(trust_score, bool(report.suspicion_flags))
            job = ReconciliationJob(affiliate_report_id=report.id, priority=priority_label)
            queue.enqueue(job, priority=priority_label)
            enqueued.append(report.id)
            logger.info(
                "Manual reconciliation job enqueued",
                affiliate_report_id=report.id,
                post_id=report.post_id,
                priority=priority_label,
                trust_bucket=bucket,
                suspicion_flags=bool(report.suspicion_flags),
                request_id=request_id
            )

        if trigger_data.post_id is not None:
            post: Post | None = db.query(Post).options(selectinload(Post.affiliate_reports), selectinload(Post.affiliate)).filter(Post.id == trigger_data.post_id).first()
            if not post:
                raise HTTPException(status_code=404, detail=f"Post {trigger_data.post_id} not found")
            # choose most recent affiliate report
            if not post.affiliate_reports:
                raise HTTPException(status_code=400, detail="Post has no affiliate reports to reconcile")
            # Determine latest report by submitted_at (fallback to id for safety)
            latest = max(
                post.affiliate_reports,
                key=lambda r: (getattr(r, "submitted_at", None) or 0, r.id)
            )
            if latest.reconciliation_log and not trigger_data.force_reprocess:
                raise HTTPException(status_code=409, detail="Latest report already reconciled. Use force_reprocess to override.")
            enqueue_for_report(latest)
        else:
            # bulk mode
            query = db.query(AffiliateReport).join(Post).options(
                selectinload(AffiliateReport.post).selectinload(Post.affiliate)
            )
            if not trigger_data.force_reprocess:
                query = query.filter(AffiliateReport.reconciliation_log == None)  # noqa: E711
            reports = query.limit(1000).all()  # safety limit
            for report in reports:
                enqueue_for_report(report)

        posts_count = len(enqueued)
        duration_ms = (time.time() - start_time) * 1000

        log_business_event(
            event_type="manual_reconciliation_triggered",
            details={
                "post_id": trigger_data.post_id,
                "force_reprocess": trigger_data.force_reprocess,
                "reports_enqueued": posts_count
            },
            request_id=request_id
        )
        log_performance(
            operation="trigger_reconciliation",
            duration_ms=duration_ms,
            additional_data={"reports_enqueued": posts_count}
        )
        return ResponseBase(
            success=True,
            message=f"Enqueued {posts_count} reconciliation job(s)",
            data={
                "reports_enqueued": posts_count,
                "affiliate_report_ids": enqueued,
                "queue_depth": queue.depth(),
            }
        )
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover
        logger.error(
            "Manual reconciliation trigger failed",
            error=str(e),
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to enqueue reconciliation")

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

@router.get(
    "/queue",
    response_model=ResponseBase,
    summary="Get reconciliation queue snapshot"
)
async def queue_snapshot(request: Request) -> ResponseBase:
    request_id = request.headers.get("X-Request-ID", "unknown")
    queue = getattr(request.app.state, "reconciliation_queue", None)  # type: ignore[attr-defined]
    if queue is None:
        raise HTTPException(status_code=503, detail="Reconciliation queue not available")
    snap = queue.snapshot()
    return ResponseBase(success=True, message="Queue snapshot", data={"snapshot": snap, "request_id": request_id})


def _build_reconciliation_result(log: ReconciliationLog) -> ReconciliationResult:
    post = log.affiliate_report.post
    # Affiliate (claimed) metrics
    from app.models.schemas.base import UnifiedMetrics
    affiliate_metrics = UnifiedMetrics(
        views=log.affiliate_report.claimed_views,
        clicks=log.affiliate_report.claimed_clicks,
        conversions=log.affiliate_report.claimed_conversions,
        post_url=post.url,
        platform_name=post.platform.name if post.platform else "unknown",
    timestamp=log.affiliate_report.submitted_at,  # type: ignore[arg-type]
        source="affiliate_claim",
    )
    platform_metrics = None
    if log.platform_report:
        pr = log.platform_report
        platform_metrics = UnifiedMetrics(
            views=pr.views,
            clicks=pr.clicks,
            conversions=pr.conversions,
            post_url=post.url,
            platform_name=post.platform.name if post.platform else "unknown",
            timestamp=pr.fetched_at,  # type: ignore[arg-type]
            source="platform_api",
        )
    return ReconciliationResult(
        id=log.id,
        affiliate_report_id=log.affiliate_report_id,
        platform_report_id=log.platform_report_id,
        status=log.status.value,
        discrepancy_level=log.discrepancy_level.value if log.discrepancy_level else None,
        views_discrepancy=log.views_discrepancy,
        clicks_discrepancy=log.clicks_discrepancy,
        conversions_discrepancy=log.conversions_discrepancy,
        views_diff_pct=float(log.views_diff_pct) if log.views_diff_pct is not None else None,
        clicks_diff_pct=float(log.clicks_diff_pct) if log.clicks_diff_pct is not None else None,
        conversions_diff_pct=float(log.conversions_diff_pct) if log.conversions_diff_pct is not None else None,
        notes=log.notes,
    processed_at=log.processed_at,  # type: ignore[arg-type]
        affiliate_metrics=affiliate_metrics,
        platform_metrics=platform_metrics,
    )


@router.get(
    "/logs/{affiliate_report_id}",
    response_model=ReconciliationResult,
    summary="Get reconciliation result for a specific affiliate report"
)
async def get_reconciliation_result(
    affiliate_report_id: int,
    request: Request,
    db: Session = Depends(get_db)
) -> ReconciliationResult:
    log_entry = db.query(ReconciliationLog).options(
        selectinload(ReconciliationLog.affiliate_report).selectinload(AffiliateReport.post).selectinload(Post.platform),
        selectinload(ReconciliationLog.platform_report)
    ).filter(ReconciliationLog.affiliate_report_id == affiliate_report_id).first()
    if not log_entry:
        raise HTTPException(status_code=404, detail="Reconciliation log not found for affiliate report")
    return _build_reconciliation_result(log_entry)

