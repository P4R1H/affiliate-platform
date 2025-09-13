from fastapi.testclient import TestClient
from app.models.db import Platform, ReconciliationLog, Affiliate
from app.models.db.affiliate_reports import SubmissionMethod
from app.services.reconciliation_engine import run_reconciliation


# Helper to install synchronous mock adapter for platform fetcher
def _install_mock_adapter(module_name: str, metrics: dict):
    mod = __import__(f"app.integrations.{module_name}", fromlist=["fetch_post_metrics"])  # noqa

    def _fetch(post_url: str):
        return metrics

    setattr(mod, "fetch_post_metrics", _fetch)
    return mod


def test_full_affiliate_submission_flow(client, db_session, platform_factory, affiliate_factory, campaign_factory):
    # Seed platform
    reddit = platform_factory("reddit")

    # Create affiliate via API (tests POST /affiliates)
    payload = {"name": "Alpha Influencer", "email": "alpha@example.com"}
    r = client.post("/api/v1/affiliates/", json=payload)
    assert r.status_code == 201, r.text
    affiliate_data = r.json()
    api_key = affiliate_data["api_key"]
    auth = {"Authorization": f"Bearer {api_key}"}
    affiliate_id = affiliate_data["id"]

    # Create campaign (DB factory uses platform ids)
    campaign = campaign_factory("Launch Campaign", [reddit.id])

    # List platforms
    r = client.get("/api/v1/platforms/")
    assert r.status_code == 200

    # Affiliate submission (perfect match scenario)
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
    post_id = sub_resp["post_id"]
    report_id = sub_resp["affiliate_report_id"]

    # Simulate platform metrics fetch (match claimed)
    _install_mock_adapter("reddit", {"views": 1000, "clicks": 50, "conversions": 5})

    # User triggers manual reconciliation (mirrors UI action)
    r = client.post("/api/v1/reconciliation/run", json={"post_id": post_id, "force_reprocess": False})
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True

    # For determinism call engine directly (background queue may be async in real system)
    run_reconciliation(db_session, report_id)

    # Fetch reconciliation results list
    r = client.get("/api/v1/reconciliation/results")
    assert r.status_code == 200

    # Verify reconciliation log reflects MATCHED
    log = db_session.query(ReconciliationLog).filter_by(affiliate_report_id=report_id).first()
    assert log is not None
    assert log.status.name == "MATCHED"

    # Trust score should have increased (perfect match trust event)
    affiliate_row = db_session.query(Affiliate).filter_by(id=affiliate_id).first()
    assert affiliate_row is not None
    assert float(affiliate_row.trust_score) >= 0.5  # default likely 0.5 baseline, ensure not decreased

    # Alerts list should be empty (no discrepancy)
    r = client.get("/api/v1/alerts/")
    assert r.status_code == 200
    assert r.json() == []

    # Metrics history endpoint
    r = client.get(f"/api/v1/submissions/{post_id}/metrics", headers=auth)
    assert r.status_code == 200
    metrics_history = r.json()
    assert len(metrics_history) == 1  # only initial submission (no subsequent updates here)
