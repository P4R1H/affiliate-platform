import time
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.db import ReconciliationLog, Alert, AffiliateReport, Post
from app.models.db.enums import ReconciliationStatus
from app.models.db.alerts import AlertType

POLL_INTERVAL = 0.05
TIMEOUT = 4.0

# Local helpers (kept inside test file for clarity and isolation)

def install_mock_adapter(module_name: str, metrics: dict | None = None, *, error: Exception | None = None):
    mod = __import__(f"app.integrations.{module_name}", fromlist=["fetch_post_metrics"])  # noqa
    def _fetch(post_url: str):
        if error:
            raise error
        return metrics
    setattr(mod, "fetch_post_metrics", _fetch)


def wait_for(predicate, *, timeout: float = TIMEOUT, interval: float = POLL_INTERVAL):
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(interval)
    return None


def test_full_system_flow(client: TestClient, db_session: Session, platform_factory, affiliate_factory, campaign_factory):
    """End-to-end system test exercising queue + worker + reconciliation logic without direct engine calls.

    Scenarios executed sequentially for a single affiliate:
      A. Perfect match -> MATCHED (trust up)
      B. Medium discrepancy (platform higher) -> DISCREPANCY_MEDIUM (trust down)
      C. Overclaim (affiliate higher) -> AFFILIATE_OVERCLAIMED + alert
      D. Partial platform data -> INCOMPLETE_PLATFORM_DATA (confidence < 1)
      E. Missing platform data (adapter error) -> MISSING_PLATFORM_DATA + retry scheduled
    Verifies trust trajectory, alert creation, retry scheduling, and worker processing path.
    """
    # Seed environment
    reddit = platform_factory("reddit")
    affiliate = affiliate_factory()
    campaign = campaign_factory("SysTest", [reddit.id])
    auth = {"Authorization": f"Bearer {affiliate.api_key}"}

    base_trust = float(affiliate.trust_score)

    # A. Perfect match
    install_mock_adapter("reddit", {"views": 100, "clicks": 10, "conversions": 1})
    pm_payload = {
        "campaign_id": campaign.id,
        "platform_id": reddit.id,
        "post_url": "https://reddit.com/r/full/a1",
        "title": "A1",
        "claimed_views": 100,
        "claimed_clicks": 10,
        "claimed_conversions": 1,
        "submission_method": "API"
    }
    r = client.post("/api/v1/submissions/", json=pm_payload, headers=auth)
    rep_match = r.json()["data"]["affiliate_report_id"]
    log_match = wait_for(lambda: db_session.query(ReconciliationLog).filter_by(affiliate_report_id=rep_match).first())
    assert log_match and log_match.status == ReconciliationStatus.MATCHED
    db_session.refresh(affiliate)
    after_match = float(affiliate.trust_score)
    assert after_match >= base_trust

    # B. Medium discrepancy (platform higher ~18%)
    install_mock_adapter("reddit", {"views": 118, "clicks": 12, "conversions": 1})
    md_payload = pm_payload | {"post_url": "https://reddit.com/r/full/b1", "claimed_views": 100, "claimed_clicks": 10}
    r = client.post("/api/v1/submissions/", json=md_payload, headers=auth)
    rep_medium = r.json()["data"]["affiliate_report_id"]
    log_medium = wait_for(lambda: db_session.query(ReconciliationLog).filter_by(affiliate_report_id=rep_medium).first())
    assert log_medium and log_medium.status == ReconciliationStatus.DISCREPANCY_MEDIUM
    db_session.refresh(affiliate)
    after_medium = float(affiliate.trust_score)
    assert after_medium < after_match

    # C. Overclaim (affiliate significantly higher)
    install_mock_adapter("reddit", {"views": 100, "clicks": 10, "conversions": 1})
    oc_payload = pm_payload | {"post_url": "https://reddit.com/r/full/c1", "claimed_views": 250, "claimed_clicks": 35, "claimed_conversions": 4}
    r = client.post("/api/v1/submissions/", json=oc_payload, headers=auth)
    rep_over = r.json()["data"]["affiliate_report_id"]
    log_over = wait_for(lambda: db_session.query(ReconciliationLog).filter_by(affiliate_report_id=rep_over).first())
    assert log_over and log_over.status == ReconciliationStatus.AFFILIATE_OVERCLAIMED
    # Alert created
    alert = db_session.query(Alert).filter_by(reconciliation_log_id=log_over.id).first()
    assert alert is not None and alert.alert_type == AlertType.HIGH_DISCREPANCY
    db_session.refresh(affiliate)
    after_over = float(affiliate.trust_score)
    assert after_over < after_medium

    # D. Partial data (one metric present)
    install_mock_adapter("reddit", {"views": 90, "clicks": None, "conversions": None})
    pd_payload = pm_payload | {"post_url": "https://reddit.com/r/full/d1", "claimed_views": 90}
    r = client.post("/api/v1/submissions/", json=pd_payload, headers=auth)
    rep_partial = r.json()["data"]["affiliate_report_id"]
    log_partial = wait_for(lambda: db_session.query(ReconciliationLog).filter_by(affiliate_report_id=rep_partial).first())
    assert log_partial and log_partial.status == ReconciliationStatus.INCOMPLETE_PLATFORM_DATA
    assert log_partial.confidence_ratio is not None and float(log_partial.confidence_ratio) < 1

    # E. Missing data (adapter error)
    install_mock_adapter("reddit", None, error=RuntimeError("fetch failed"))
    md_payload2 = pm_payload | {"post_url": "https://reddit.com/r/full/e1", "claimed_views": 70}
    r = client.post("/api/v1/submissions/", json=md_payload2, headers=auth)
    rep_missing = r.json()["data"]["affiliate_report_id"]
    log_missing = wait_for(lambda: db_session.query(ReconciliationLog).filter_by(affiliate_report_id=rep_missing).first())
    assert log_missing and log_missing.status == ReconciliationStatus.MISSING_PLATFORM_DATA
    assert log_missing.scheduled_retry_at is not None

    # Trust trajectory monotonic checkpoints
    final_trust = float(affiliate.trust_score)
    assert final_trust <= after_over <= after_medium <= after_match
    assert final_trust < base_trust or after_match > base_trust  # at least some movement occurred

    # Only one alert (overclaim)
    # Only one alert for this affiliate (overclaim). Other tests isolated, but guard by affiliate id.
    alerts = db_session.query(Alert).join(ReconciliationLog, Alert.reconciliation_log_id == ReconciliationLog.id)\
        .join(AffiliateReport, ReconciliationLog.affiliate_report_id == AffiliateReport.id)\
        .join(Post, AffiliateReport.post_id == Post.id)\
        .filter(Post.affiliate_id == affiliate.id).all()
    assert len(alerts) == 1

    # Basic sanity: all logs present
    ids = [rep_match, rep_medium, rep_over, rep_partial, rep_missing]
    assert db_session.query(ReconciliationLog).filter(ReconciliationLog.affiliate_report_id.in_(ids)).count() == 5
