"""
Alert management endpoints.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, selectinload
import time
from app.api.deps import get_db
from datetime import datetime
from app.models.db import Alert, ReconciliationLog, AlertStatus
from app.models.schemas.alerts import AlertRead, AlertResolve
from app.models.schemas.base import ResponseBase
from app.utils import get_logger, log_business_event, log_performance

router = APIRouter()
logger = get_logger(__name__)

@router.get(
    "/",
    response_model=List[Dict[str, Any]],
    summary="Get active alerts"
)
async def get_alerts(
    request: Request,
    status_filter: Optional[str] = Query(None, regex="^(OPEN|RESOLVED)$"),
    alert_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:  # order fixed: request (non-default) first
    """Get alerts with filtering and pagination."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Alerts list requested",
        status_filter=status_filter,
        alert_type=alert_type,
        limit=limit,
        offset=offset,
        request_id=request_id
    )
    
    try:
        query = db.query(Alert).options(
            selectinload(Alert.reconciliation_log)
        )
        
        if status_filter:
            query = query.filter(Alert.status == status_filter)
        
        if alert_type:
            query = query.filter(Alert.alert_type == alert_type)
        
        alerts = query.order_by(Alert.created_at.desc()).offset(offset).limit(limit).all()
        
        # Format alerts
        formatted_alerts = []
        for alert in alerts:
            formatted_alerts.append({
                "id": alert.id,
                "reconciliation_log_id": alert.reconciliation_log_id,
                "alert_type": alert.alert_type,
                "title": alert.title,
                "message": alert.message,
                "threshold_breached": alert.threshold_breached,
                "status": alert.status,
                "resolved_by": alert.resolved_by,
                "resolved_at": alert.resolved_at,
                "resolution_notes": alert.resolution_notes,
                "created_at": alert.created_at
            })
        
        # Log performance
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="get_alerts",
            duration_ms=duration_ms,
            additional_data={"alerts_returned": len(formatted_alerts)}
        )
        
        logger.info(
            "Alerts list completed",
            alerts_returned=len(formatted_alerts),
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        return formatted_alerts
        
    except Exception as e:
        logger.error(
            "Alerts list failed",
            error=str(e),
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving alerts"
        )

@router.put(
    "/{alert_id}/resolve",
    response_model=ResponseBase,
    summary="Resolve an alert"
)
async def resolve_alert(
    alert_id: int,
    resolution_data: AlertResolve,
    request: Request,
    db: Session = Depends(get_db)
) -> ResponseBase:
    """Resolve an alert with resolution notes."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Alert resolution started",
        alert_id=alert_id,
        resolved_by=resolution_data.resolved_by,
        request_id=request_id
    )
    
    try:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            logger.warning(
                "Alert resolution failed: alert not found",
                alert_id=alert_id,
                request_id=request_id
            )
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert with id {alert_id} not found")

        current_status = getattr(alert.status, "value", alert.status)
        if str(current_status) == AlertStatus.RESOLVED.value:
            logger.warning(
                "Alert resolution failed: already resolved",
                alert_id=alert_id,
                request_id=request_id
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Alert is already resolved")

        alert.status = AlertStatus.RESOLVED  # type: ignore[assignment]
        alert.resolved_by = resolution_data.resolved_by  # type: ignore[assignment]
        alert.resolved_at = datetime.utcnow()  # type: ignore[assignment]
        alert.resolution_notes = resolution_data.resolution_notes  # type: ignore[assignment]
        db.commit()
        
        # Log business event
        log_business_event(
            event_type="alert_resolved",
            details={
                "alert_id": alert_id,
                "alert_type": alert.alert_type,
                "resolved_by": resolution_data.resolved_by,
                "has_notes": bool(resolution_data.resolution_notes)
            },
            request_id=request_id
        )
        
        # Log performance
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="resolve_alert",
            duration_ms=duration_ms,
            additional_data={"alert_id": alert_id}
        )
        
        logger.info(
            "Alert resolved successfully",
            alert_id=alert_id,
            resolved_by=resolution_data.resolved_by,
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        return ResponseBase(
            success=True,
            message="Alert resolved successfully",
            data={
                "alert_id": alert_id,
                "resolved_by": resolution_data.resolved_by,
                "resolved_at": alert.resolved_at
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Alert resolution failed",
            alert_id=alert_id,
            error=str(e),
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during alert resolution"
        )

@router.get(
    "/stats",
    response_model=Dict[str, Any],
    summary="Get alert statistics"
)
async def get_alert_stats(
    request: Request,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get alert statistics and summary."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logger.info(
        "Alert statistics requested",
        request_id=request_id
    )
    
    try:
        from sqlalchemy import func
        
        # Get alert counts by status
        status_counts = db.query(
            Alert.status,
            func.count(Alert.id).label('count')
        ).group_by(Alert.status).all()
        
        # Get alert counts by type
        type_counts = db.query(
            Alert.alert_type,
            func.count(Alert.id).label('count')
        ).group_by(Alert.alert_type).all()
        
        # Get recent alerts (last 24 hours)
        from datetime import datetime, timedelta
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_count = db.query(Alert).filter(Alert.created_at >= yesterday).count()
        
        stats = {
            "total_alerts": db.query(Alert).count(),
            "by_status": {status: count for status, count in status_counts},
            "by_type": {alert_type: count for alert_type, count in type_counts},
            "recent_24h": recent_count,
            "generated_at": datetime.utcnow().isoformat()
        }
        
        # Log performance
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            operation="get_alert_stats",
            duration_ms=duration_ms
        )
        
        logger.info(
            "Alert statistics completed",
            total_alerts=stats["total_alerts"],
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        return stats
        
    except Exception as e:
        logger.error(
            "Alert statistics failed",
            error=str(e),
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving alert statistics"
        )