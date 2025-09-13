from fastapi.testclient import TestClient
from app.models.db import Platform, Campaign, Affiliate, Post, AffiliateReport, ReconciliationLog, Alert
from app.models.db.alerts import AlertType, AlertStatus
from app.models.db.reconciliation_logs import ReconciliationStatus, DiscrepancyLevel
from app.models.db.affiliate_reports import SubmissionMethod
from datetime import date


def test_duplicate_affiliate_email(client):
    payload = {"name": "User1", "email": "dup@example.com"}
    r = client.post("/api/v1/affiliates/", json=payload)
    assert r.status_code == 201
    r2 = client.post("/api/v1/affiliates/", json=payload)
    assert r2.status_code == 409


def test_post_duplicate_submission_conflict(client, platform_factory, affiliate_factory, campaign_factory):
    reddit = platform_factory("reddit")
    affiliate = affiliate_factory()
    campaign = campaign_factory("Camp1", [reddit.id])
    auth = {"Authorization": f"Bearer {affiliate.api_key}"}

    submission_payload = {
        "campaign_id": campaign.id,
        "platform_id": reddit.id,
        "post_url": "https://reddit.com/r/test/dup",
        "title": "Review",
        "claimed_views": 10,
        "claimed_clicks": 1,
        "claimed_conversions": 0,
        "submission_method": SubmissionMethod.API.value
    }
    r = client.post("/api/v1/submissions/", json=submission_payload, headers=auth)
    assert r.status_code == 201
    r2 = client.post("/api/v1/submissions/", json=submission_payload, headers=auth)
    assert r2.status_code == 409


def test_post_submission_platform_not_in_campaign(client, platform_factory, affiliate_factory, campaign_factory):
    reddit = platform_factory("reddit")
    instagram = platform_factory("instagram")
    affiliate = affiliate_factory()
    campaign = campaign_factory("Camp2", [reddit.id])  # instagram NOT in campaign
    auth = {"Authorization": f"Bearer {affiliate.api_key}"}

    submission_payload = {
        "campaign_id": campaign.id,
        "platform_id": instagram.id,
        "post_url": "https://instagram.com/p/123",
        "claimed_views": 5,
        "claimed_clicks": 0,
        "claimed_conversions": 0,
        "submission_method": SubmissionMethod.API.value
    }
    r = client.post("/api/v1/submissions/", json=submission_payload, headers=auth)
    assert r.status_code == 400


def test_alert_resolution_flow(client, db_session, platform_factory, affiliate_factory, campaign_factory):
    # Create data chain manually to simulate discrepancy alert then resolve
    reddit = platform_factory("reddit")
    affiliate = affiliate_factory()
    campaign = campaign_factory("Camp3", [reddit.id])
    # Create post + affiliate report
    post = Post(campaign_id=campaign.id, affiliate_id=affiliate.id, platform_id=reddit.id, url="http://u/1")
    db_session.add(post)
    db_session.flush()
    report = AffiliateReport(post_id=post.id, claimed_views=1000, claimed_clicks=100, claimed_conversions=10, submission_method=SubmissionMethod.API)
    db_session.add(report)
    db_session.flush()
    rec = ReconciliationLog(
        affiliate_report_id=report.id,
        status=ReconciliationStatus.DISCREPANCY_HIGH,
        discrepancy_level=DiscrepancyLevel.HIGH,
        views_discrepancy=500,
        clicks_discrepancy=50,
        conversions_discrepancy=5,
        views_diff_pct=50.0,
        clicks_diff_pct=50.0,
        conversions_diff_pct=50.0,
        notes="Large discrepancy synthetic test"
    )
    db_session.add(rec)
    db_session.flush()
    alert = Alert(
        reconciliation_log_id=rec.id,
        alert_type=AlertType.HIGH_DISCREPANCY,
        title="High discrepancy detected",
        message="Affiliate overclaimed metrics",
        threshold_breached={"views_pct": 50},
    )
    db_session.add(alert)
    db_session.commit()

    # GET alerts
    r = client.get("/api/v1/alerts/")
    assert r.status_code == 200
    alerts_all = r.json()
    # Filter to alerts for this affiliate's reconciliation log only (avoid cross-test leakage if isolation missed)
    alerts = [a for a in alerts_all if a.get("reconciliation_log_id") == rec.id]
    assert len(alerts) == 1, f"Expected 1 alert for this test rec, got {len(alerts)} total={len(alerts_all)}"

    # Resolve alert
    resolution_payload = {"resolved_by": "qa_user", "resolution_notes": "Validated issue"}
    alert_id = alerts[0]["id"]
    r = client.put(f"/api/v1/alerts/{alert_id}/resolve", json=resolution_payload)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
