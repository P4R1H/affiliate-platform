"""
Analytics endpoints (MVP).
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from app.api.deps import get_db, get_campaign_if_authorized
from app.models.db import Campaign, Post, PlatformReport, AffiliateReport, ReconciliationLog, Alert, Platform
from app.models.db.enums import ReconciliationStatus
from app.utils import get_logger, log_performance
import time

router = APIRouter()
logger = get_logger(__name__)

SUCCESS_STATUSES = {
    ReconciliationStatus.MATCHED,
    ReconciliationStatus.DISCREPANCY_LOW,
}

@router.get("/campaigns/{campaign_id}", summary="Get essential campaign analytics")
async def get_campaign_analytics(
    campaign_id: int,
    request: Request,
    campaign: Campaign = Depends(get_campaign_if_authorized),
    db: Session = Depends(get_db)
):
    """Get aggregated analytics for a campaign including posts and platform metrics."""
    start = time.time()
    request_id = request.headers.get("X-Request-ID", "unknown")

    # campaign already validated + RBAC enforced by dependency

    # Aggregates: posts + platform metrics
    totals_query = (
        db.query(
            func.count(Post.id).label("posts"),
            func.coalesce(func.sum(PlatformReport.views), 0).label("views"),
            func.coalesce(func.sum(PlatformReport.clicks), 0).label("clicks"),
            func.coalesce(func.sum(PlatformReport.conversions), 0).label("conversions"),
        )
        .join(PlatformReport, PlatformReport.post_id == Post.id, isouter=True)
        .filter(Post.campaign_id == campaign_id)
    )
    posts_total, views_total, clicks_total, conversions_total = totals_query.one()

    # Reconciliation health
    # Count affiliate reports linked to campaign posts
    recon_query = (
        db.query(
            func.count(AffiliateReport.id).label("reports"),
            func.sum(
                case(
                    (ReconciliationLog.status.in_(tuple(s.value for s in SUCCESS_STATUSES)), 1), else_=0
                )
            ).label("success_reports"),
            func.sum(
                case(((ReconciliationLog.id.is_(None)), 1), else_=0)  # no log yet
            ).label("pending_reports"),
        )
        .join(Post, Post.id == AffiliateReport.post_id)
        .join(ReconciliationLog, ReconciliationLog.affiliate_report_id == AffiliateReport.id, isouter=True)
        .filter(Post.campaign_id == campaign_id)
    )
    reports_count, success_reports, pending_reports = recon_query.one()
    success_reports = success_reports or 0
    pending_reports = pending_reports or 0
    reconciled_count = reports_count - pending_reports
    success_rate = float(success_reports) / reconciled_count if reconciled_count > 0 else None

    # Platform breakdown
    platform_rows = (
        db.query(
            Platform.id,
            Platform.name,
            func.coalesce(func.sum(PlatformReport.views), 0),
            func.coalesce(func.sum(PlatformReport.clicks), 0),
            func.coalesce(func.sum(PlatformReport.conversions), 0),
        )
        .join(Post, Post.platform_id == Platform.id)
        .join(PlatformReport, PlatformReport.post_id == Post.id, isouter=True)
        .filter(Post.campaign_id == campaign_id)
        .group_by(Platform.id, Platform.name)
        .all()
    )
    platform_breakdown = [
        {
            "platform_id": pid,
            "platform_name": name,
            "views": int(views or 0),
            "clicks": int(clicks or 0),
            "conversions": int(conversions or 0),
        }
        for pid, name, views, clicks, conversions in platform_rows
    ]

    # Recent alerts (limit 5) - join through reconciliation_log -> affiliate_report -> post -> campaign
    recent_alerts = (
        db.query(
            Alert.id,
            Alert.severity,
            Alert.status,
            Alert.title,
            Alert.created_at,
        )
        .join(ReconciliationLog, ReconciliationLog.id == Alert.reconciliation_log_id)
        .join(AffiliateReport, AffiliateReport.id == ReconciliationLog.affiliate_report_id)
        .join(Post, Post.id == AffiliateReport.post_id)
        .filter(Post.campaign_id == campaign_id)
        .order_by(Alert.created_at.desc())
        .limit(5)
        .all()
    )
    alerts_serialized = [
        {
            "id": a_id,
            "severity": severity,
            "status": status,
            "title": title,
            "created_at": created_at,
        }
        for a_id, severity, status, title, created_at in recent_alerts
    ]

    duration_ms = (time.time() - start) * 1000
    log_performance(
        operation="get_campaign_analytics",
        duration_ms=duration_ms,
        additional_data={
            "campaign_id": campaign_id,
            "posts": posts_total,
            "reports": reports_count,
        },
    )

    logger.info(
        "Campaign analytics computed",
        campaign_id=campaign_id,
        request_id=request_id,
        duration_ms=duration_ms,
    )

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign.name,
        "client_id": campaign.client_id,
        "totals": {
            "posts": posts_total,
            "views": int(views_total or 0),
            "clicks": int(clicks_total or 0),
            "conversions": int(conversions_total or 0),
        },
        "reconciliation": {
            "success_rate": round(success_rate, 4) if success_rate is not None else None,
            "pending_reports": int(pending_reports),
            "total_reconciled": int(reconciled_count),
        },
        "platform_breakdown": platform_breakdown,
        "recent_alerts": alerts_serialized,
        "request_id": request_id,
    }
