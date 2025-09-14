from fastapi.testclient import TestClient
from app.models.db import Platform, ReconciliationLog, User, Post
from app.models.db.affiliate_reports import SubmissionMethod
from sqlalchemy.orm import Session
import time


# Helper polling for worker-produced reconciliation log
def _wait_for_log(db: Session, report_id: int, timeout: float = 3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        db.expire_all()
        log = db.query(ReconciliationLog).filter_by(affiliate_report_id=report_id).first()
        if log and log.status is not None:
            return log
        time.sleep(0.05)
    return None


# Monkeypatch helper kept local to avoid cross‑test coupling
def _install_mock_adapter(module_name: str, metrics: dict):
    mod = __import__(f"app.integrations.{module_name}", fromlist=["fetch_post_metrics"])  # noqa

    def _fetch(post_url: str):
        return metrics

    setattr(mod, "fetch_post_metrics", _fetch)
    return mod


def test_full_affiliate_submission_flow(client: TestClient, db_session: Session, platform_factory, affiliate_factory, campaign_factory):
    # Seed platform
    reddit = platform_factory("reddit")

    # Create affiliate via API (tests POST /users)
    payload = {"name": "Alpha Influencer", "email": "alpha@example.com", "role": "AFFILIATE"}
    r = client.post("/api/v1/users/", json=payload)
    assert r.status_code == 201, r.text
    affiliate_data = r.json()
    api_key = affiliate_data["api_key"]
    affiliate_id = affiliate_data["id"]
    auth = {"Authorization": f"Bearer {api_key}"}

    # Create campaign (DB factory uses platform ids)
    campaign = campaign_factory("Launch Campaign", [reddit.id])

    # List platforms
    r = client.get("/api/v1/platforms/")
    assert r.status_code == 200

    # Perfect match submission – patch adapter BEFORE submit so worker sees it
    _install_mock_adapter("reddit", {"views": 1000, "clicks": 50, "conversions": 5})
    submission_payload = {
        "campaign_id": campaign.id,
        "platform_id": reddit.id,
        "post_url": "https://reddit.com/r/test/abc123",
        "title": "Great Product!",
        "claimed_views": 1000,
        "claimed_clicks": 50,
        "claimed_conversions": 5,
        "evidence_data": {"screenshots": ["http://img.test/1.png"]},
        "submission_method": SubmissionMethod.API.value,
    }
    r = client.post("/api/v1/submissions/", json=submission_payload, headers=auth)
    assert r.status_code == 201, r.text
    sub_resp = r.json()["data"]
    report_id = sub_resp["affiliate_report_id"]

    log = _wait_for_log(db_session, report_id)
    assert log is not None, "Reconciliation log not produced by worker"
    assert log.status.name == "MATCHED"

    affiliate_row = db_session.query(User).filter_by(id=affiliate_id).first()
    assert affiliate_row is not None
    assert affiliate_row.trust_score is not None and float(affiliate_row.trust_score) >= 0.5  # default likely 0.5 baseline, ensure not decreased

    r = client.get(f"/api/v1/submissions/{sub_resp['post_id']}/metrics", headers=auth)
    assert r.status_code == 200
    metrics_history = r.json()
    assert len(metrics_history) == 1  # only initial submission (no subsequent updates here)

    # Check alerts for this specific affiliate only (other tests may leave alerts in DB)
    r = client.get("/api/v1/alerts/")
    assert r.status_code == 200
    alerts = r.json()
    
    # Filter alerts for this specific affiliate by checking if any alert relates to our user
    affiliate_alerts = []
    if alerts:
        for alert in alerts:
            # Check if this alert relates to our user by checking the reconciliation log
            if 'reconciliation_log_id' in alert:
                log = db_session.query(ReconciliationLog).filter_by(id=alert['reconciliation_log_id']).first()
                if log and log.affiliate_report:
                    post = db_session.query(Post).filter_by(id=log.affiliate_report.post_id).first()
                    if post and post.user_id == affiliate_id:
                        affiliate_alerts.append(alert)
    
    assert affiliate_alerts == [], f"Expected no alerts for this affiliate, but found: {affiliate_alerts}"
