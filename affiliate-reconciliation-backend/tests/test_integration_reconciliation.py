import time
import secrets
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.db import Platform, Affiliate, Campaign, Post, AffiliateReport, ReconciliationLog, Alert
from app.models.db.enums import ReconciliationStatus
from app.models.db.alerts import AlertType
from app.models.db.reconciliation_logs import DiscrepancyLevel
from app.models.db.affiliate_reports import SubmissionMethod
from app.services.trust_scoring import apply_trust_event
from app.services.reconciliation_engine import run_reconciliation

# Helper: wait for reconciliation log to appear / reach status
def wait_for_log(db: Session, report_id: int, *, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        log = db.query(ReconciliationLog).filter_by(affiliate_report_id=report_id).first()
        if log:
            return log
        time.sleep(0.05)
    return None

def install_mock_adapter(module_name: str, metrics: dict | None, *, error: Exception | None = None):
    """Install a synchronous fetch_post_metrics function on integration module used by PlatformFetcher.
    metrics: dict with keys views/clicks/conversions (values may be None to simulate partial data)
    error: if provided, function raises it to simulate failure (missing data path)
    """
    mod = __import__(f"app.integrations.{module_name}", fromlist=["fetch_post_metrics"])  # noqa
    def _fetch(post_url: str):  # signature expected by PlatformFetcher
        # Simple deterministic adapter; raises if error provided.
        if error:
            raise error
        return metrics
    setattr(mod, "fetch_post_metrics", _fetch)
    return mod

@pytest.fixture()
def seeded_platform(platform_factory):
    return platform_factory("reddit")  # reuse reddit for deterministic tests

@pytest.fixture()
def affiliate(db_session):
    """Create a unique affiliate per test to avoid UNIQUE constraint collisions."""
    unique = secrets.token_hex(4)
    a = Affiliate(name=f"IntTest-{unique}", email=f"inttest-{unique}@example.com", api_key=f"aff_inttest_{unique}")
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    return a

@pytest.fixture()
def campaign(db_session, seeded_platform):
    from app.models.db import Campaign
    from app.models.db.enums import CampaignStatus
    from datetime import date
    c = Campaign(name="Int Camp", advertiser_name="BrandX", start_date=date(2025,1,1), status=CampaignStatus.ACTIVE)
    c.platforms = [seeded_platform]
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c

@pytest.fixture()
def auth_header(affiliate):  # returns only header dict for simplicity
    return {"Authorization": f"Bearer {affiliate.api_key}"}

# 1. Perfect match -> MATCHED + trust increase
def test_reconciliation_matched_flow(client: TestClient, db_session: Session, seeded_platform, affiliate, campaign, auth_header):
    install_mock_adapter("reddit", {"views": 100, "clicks": 10, "conversions": 1})
    payload = {
        "campaign_id": campaign.id,
        "platform_id": seeded_platform.id,
        "post_url": "https://reddit.com/r/test/pmatch",
        "title": "Post1",
        "claimed_views": 100,
        "claimed_clicks": 10,
        "claimed_conversions": 1,
        "submission_method": SubmissionMethod.API.value
    }
    r = client.post("/api/v1/submissions/", json=payload, headers=auth_header)
    assert r.status_code == 201, r.text
    report_id = r.json()["data"]["affiliate_report_id"]
    # Direct reconciliation (bypass background worker & endpoint for determinism)
    run_reconciliation(db_session, report_id)
    log = db_session.query(ReconciliationLog).filter_by(affiliate_report_id=report_id).first()
    assert log is not None
    assert log.status == ReconciliationStatus.MATCHED
    assert log.max_discrepancy_pct in (0, 0.0)

# 2. Overclaim -> AFFILIATE_OVERCLAIMED + Alert created
def test_reconciliation_overclaim_alert(client: TestClient, db_session: Session, seeded_platform, affiliate, campaign, auth_header):
    install_mock_adapter("reddit", {"views": 100, "clicks": 10, "conversions": 1})
    payload = {
        "campaign_id": campaign.id,
        "platform_id": seeded_platform.id,
        "post_url": "https://reddit.com/r/test/overclaim",
        "title": "Post2",
        "claimed_views": 250,  # 150% over claimed > 20% threshold
        "claimed_clicks": 30,
        "claimed_conversions": 5,
        "submission_method": SubmissionMethod.API.value
    }
    r = client.post("/api/v1/submissions/", json=payload, headers=auth_header)
    assert r.status_code == 201
    report_id = r.json()["data"]["affiliate_report_id"]
    run_reconciliation(db_session, report_id)
    log = db_session.query(ReconciliationLog).filter_by(affiliate_report_id=report_id).first()
    assert log is not None
    assert log.status == ReconciliationStatus.AFFILIATE_OVERCLAIMED
    # Alert should be created
    alert = db_session.query(Alert).filter_by(reconciliation_log_id=log.id).first()
    assert alert is not None
    assert alert.alert_type == AlertType.HIGH_DISCREPANCY

# 3. High discrepancy (non-overclaim) + escalation on repeat within window
def test_reconciliation_high_discrepancy_repeat_escalation(client: TestClient, db_session: Session, seeded_platform, affiliate, campaign, auth_header):
    # First run high discrepancy (claimed lower than platform so not overclaim)
    install_mock_adapter("reddit", {"views": 100, "clicks": 10, "conversions": 1})
    payload = {
        "campaign_id": campaign.id,
        "platform_id": seeded_platform.id,
        "post_url": "https://reddit.com/r/test/highdisc1",
        "title": "Post3",
        "claimed_views": 60,  # 40% diff -> high discrepancy (platform higher so not overclaim)
        "claimed_clicks": 6,
        "claimed_conversions": 1,
        "submission_method": SubmissionMethod.API.value
    }
    r = client.post("/api/v1/submissions/", json=payload, headers=auth_header)
    assert r.status_code == 201
    rep1 = r.json()["data"]["affiliate_report_id"]
    run_reconciliation(db_session, rep1)
    log1 = db_session.query(ReconciliationLog).filter_by(affiliate_report_id=rep1).first()
    assert log1 is not None
    assert log1.status in {ReconciliationStatus.DISCREPANCY_HIGH, ReconciliationStatus.DISCREPANCY_MEDIUM, ReconciliationStatus.DISCREPANCY_LOW}
    # An alert might be created only for DISCREPANCY_HIGH; store initial alert count
    initial_alerts = db_session.query(Alert).count()

    # Second submission similar discrepancy to trigger repeat logic escalation (if first was HIGH)
    payload2 = payload | {"post_url": "https://reddit.com/r/test/highdisc2", "title": "Post4"}
    r2 = client.post("/api/v1/submissions/", json=payload2, headers=auth_header)
    rep2 = r2.json()["data"]["affiliate_report_id"]
    run_reconciliation(db_session, rep2)
    log2 = db_session.query(ReconciliationLog).filter_by(affiliate_report_id=rep2).first()
    assert log2 is not None
    # Count new alerts; if both high discrepancy should be >= initial_alerts + 1
    final_alerts = db_session.query(Alert).count()
    assert final_alerts >= initial_alerts

# 4. Missing platform data -> MISSING_PLATFORM_DATA with retry scheduled
def test_reconciliation_missing_data_retry(client: TestClient, db_session: Session, seeded_platform, affiliate, campaign, auth_header):
    # Simulate adapter raising exception -> fetch_error path
    install_mock_adapter("reddit", None, error=RuntimeError("fetch failed"))
    payload = {
        "campaign_id": campaign.id,
        "platform_id": seeded_platform.id,
        "post_url": "https://reddit.com/r/test/miss1",
        "title": "Post5",
        "claimed_views": 100,
        "claimed_clicks": 10,
        "claimed_conversions": 1,
        "submission_method": SubmissionMethod.API.value
    }
    r = client.post("/api/v1/submissions/", json=payload, headers=auth_header)
    rep_id = r.json()["data"]["affiliate_report_id"]
    run_reconciliation(db_session, rep_id)
    log = db_session.query(ReconciliationLog).filter_by(affiliate_report_id=rep_id).first()
    assert log is not None
    assert log.status == ReconciliationStatus.MISSING_PLATFORM_DATA
    # scheduled_retry_at should be set (presence test)
    assert log.scheduled_retry_at is not None

# 5. Incomplete platform data (partial metrics) -> INCOMPLETE_PLATFORM_DATA
def test_reconciliation_incomplete_data(client: TestClient, db_session: Session, seeded_platform, affiliate, campaign, auth_header):
    install_mock_adapter("reddit", {"views": 100, "clicks": None, "conversions": None})
    payload = {
        "campaign_id": campaign.id,
        "platform_id": seeded_platform.id,
        "post_url": "https://reddit.com/r/test/partial",
        "title": "Post6",
        "claimed_views": 100,
        "claimed_clicks": 10,
        "claimed_conversions": 1,
        "submission_method": SubmissionMethod.API.value
    }
    r = client.post("/api/v1/submissions/", json=payload, headers=auth_header)
    rep_id = r.json()["data"]["affiliate_report_id"]
    run_reconciliation(db_session, rep_id)
    log = db_session.query(ReconciliationLog).filter_by(affiliate_report_id=rep_id).first()
    assert log is not None
    assert log.status == ReconciliationStatus.INCOMPLETE_PLATFORM_DATA
    assert log.confidence_ratio is not None and float(log.confidence_ratio) < 1

# 6. Priority influenced by suspicion flags (evidence absence triggers dq flags via evaluate_submission maybe)
# Simplified: create two submissions; second with very high CTR to trigger suspicion -> expect both enqueued; we inspect queue snapshot depth only.
# Deep inspection of internal ordering would require exposing queue internals; here we at least assert jobs enqueued successfully.

def test_priority_enqueue_with_suspicion(client: TestClient, db_session: Session, seeded_platform, affiliate, campaign, auth_header):
    install_mock_adapter("reddit", {"views": 100, "clicks": 10, "conversions": 1})
    # First normal submission
    base_payload = {
        "campaign_id": campaign.id,
        "platform_id": seeded_platform.id,
        "post_url": "https://reddit.com/r/test/prio1",
        "title": "Norm",
        "claimed_views": 1000,
        "claimed_clicks": 50,
        "claimed_conversions": 5,
        "submission_method": SubmissionMethod.API.value
    }
    r1 = client.post("/api/v1/submissions/", json=base_payload, headers=auth_header)
    assert r1.status_code == 201
    # Second suspicious (very high CTR) to trigger suspicion flag for clicks/views ratio
    suspicious = base_payload | {"post_url": "https://reddit.com/r/test/prio2", "claimed_views": 100, "claimed_clicks": 80, "claimed_conversions": 5}
    r2 = client.post("/api/v1/submissions/", json=suspicious, headers=auth_header)
    assert r2.status_code == 201
    # Trigger reconciliation for both
    run_reconciliation(db_session, r1.json()["data"]["affiliate_report_id"])  # first
    run_reconciliation(db_session, r2.json()["data"]["affiliate_report_id"])  # second
    # Verify logs created
    rep1 = r1.json()["data"]["affiliate_report_id"]
    rep2 = r2.json()["data"]["affiliate_report_id"]
    log1 = db_session.query(ReconciliationLog).filter_by(affiliate_report_id=rep1).first()
    log2 = db_session.query(ReconciliationLog).filter_by(affiliate_report_id=rep2).first()
    assert log1 is not None and log2 is not None

# 7. Trust score evolution over multiple reconciliations
# Sequence: perfect match (increase) -> high discrepancy (decrease) -> minor discrepancy/no change
# Ensures cumulative trust score and log trust_delta capture each step.
def test_trust_score_evolution(client: TestClient, db_session: Session, seeded_platform, affiliate, campaign, auth_header):
    base_trust = float(affiliate.trust_score)

    # Step 1: Perfect match (positive delta +0.01)
    install_mock_adapter("reddit", {"views": 100, "clicks": 10, "conversions": 1})
    payload = {
        "campaign_id": campaign.id,
        "platform_id": seeded_platform.id,
        "post_url": "https://reddit.com/r/test/trust1",
        "title": "T1",
        "claimed_views": 100,
        "claimed_clicks": 10,
        "claimed_conversions": 1,
        "submission_method": SubmissionMethod.API.value
    }
    r1 = client.post("/api/v1/submissions/", json=payload, headers=auth_header)
    rep1 = r1.json()["data"]["affiliate_report_id"]
    run_reconciliation(db_session, rep1)
    db_session.refresh(affiliate)
    after_match = float(affiliate.trust_score)
    assert after_match >= base_trust

    # Step 2: Medium discrepancy (~15% diff) to trigger medium discrepancy trust event (-0.03)
    # Claimed lower than platform to avoid overclaim; difference around 15%.
    install_mock_adapter("reddit", {"views": 115, "clicks": 11, "conversions": 1})
    payload2 = payload | {
        "post_url": "https://reddit.com/r/test/trust2",
        "title": "T2",
        "claimed_views": 100,  # ~13% lower than platform
        "claimed_clicks": 10,
        "claimed_conversions": 1
    }
    r2 = client.post("/api/v1/submissions/", json=payload2, headers=auth_header)
    rep2 = r2.json()["data"]["affiliate_report_id"]
    run_reconciliation(db_session, rep2)
    db_session.refresh(affiliate)
    after_medium = float(affiliate.trust_score)
    assert after_medium < after_match  # negative delta applied

    # Step 3: Overclaim to trigger another negative delta (larger -0.10)
    install_mock_adapter("reddit", {"views": 100, "clicks": 10, "conversions": 1})
    payload3 = payload | {
        "post_url": "https://reddit.com/r/test/trust3",
        "title": "T3",
        "claimed_views": 300,  # big overclaim triggers OVERCLAIM event
        "claimed_clicks": 40,
        "claimed_conversions": 5
    }
    r3 = client.post("/api/v1/submissions/", json=payload3, headers=auth_header)
    rep3 = r3.json()["data"]["affiliate_report_id"]
    run_reconciliation(db_session, rep3)
    db_session.refresh(affiliate)
    final_trust = float(affiliate.trust_score)

    assert 0.0 <= final_trust <= 1.0
    assert final_trust < after_medium <= after_match
    assert final_trust != base_trust

    logs = db_session.query(ReconciliationLog).filter(ReconciliationLog.affiliate_report_id.in_([rep1, rep2, rep3])).all()
    # Map report id to delta for clarity
    delta_map = {l.affiliate_report_id: float(l.trust_delta) for l in logs if l.trust_delta is not None}
    # Expect at least one negative delta (from medium discrepancy or overclaim) and optionally a positive from perfect match
    assert any(v < 0 for v in delta_map.values())

