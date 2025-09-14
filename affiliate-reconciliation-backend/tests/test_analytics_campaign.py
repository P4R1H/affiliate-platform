import secrets
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.db import (
    User,
    Campaign,
    Post,
    AffiliateReport,
    PlatformReport,
    ReconciliationLog,
    Alert,
    Platform,
)
from app.models.db.enums import UserRole, ReconciliationStatus
from app.models.db.affiliate_reports import SubmissionMethod
from app.models.db.alerts import AlertType

def seed_campaign_with_data(
    db: Session,
    campaign: Campaign,
    platform: Platform,
    *,
    matched: int = 1,
    low: int = 1,
    pending: int = 1,
    over: int = 1,
):
    """Create posts + reports + logs to exercise aggregation logic.
    matched -> MATCHED
    low -> DISCREPANCY_LOW
    pending -> AffiliateReport without ReconciliationLog
    over -> AFFILIATE_OVERCLAIMED (not success)
    Each creates one post / report.
    Also attaches PlatformReport metrics so totals aggregate.
    """
    # Helper to add one
    creator = db.query(User).filter(User.id == campaign.created_by).first()
    assert creator is not None, "Campaign creator must exist"

    def add_case(status: ReconciliationStatus | None):  # closure uses validated creator
        p = Post(
            campaign_id=campaign.id,
            user_id=creator.id,
            platform_id=platform.id,
            url=f"https://example.com/{secrets.token_hex(3)}",
        )
        db.add(p)
        db.flush()
        ar = AffiliateReport(
            post_id=p.id,
            claimed_views=100,
            claimed_clicks=10,
            claimed_conversions=1,
            submission_method=SubmissionMethod.API,
        )
        db.add(ar)
        db.flush()
        # platform report
        pr = PlatformReport(
            post_id=p.id, platform_id=platform.id, views=100, clicks=10, conversions=1
        )
        db.add(pr)
        db.flush()
        if status is not None:
            log = ReconciliationLog(
                affiliate_report_id=ar.id, platform_report_id=pr.id, status=status
            )
            db.add(log)
            # add alert for overclaim for coverage
            if status == ReconciliationStatus.AFFILIATE_OVERCLAIMED:
                alert = Alert(
                    reconciliation_log=log,
                    user_id=creator.id,
                    platform_id=platform.id,
                    alert_type=AlertType.HIGH_DISCREPANCY,
                    title="Overclaim",
                    message="Overclaim detected",
                )
                db.add(alert)
        db.flush()
    # loops
    for _ in range(matched):
        add_case(ReconciliationStatus.MATCHED)
    for _ in range(low):
        add_case(ReconciliationStatus.DISCREPANCY_LOW)
    for _ in range(over):
        add_case(ReconciliationStatus.AFFILIATE_OVERCLAIMED)
    for _ in range(pending):
        add_case(None)
    db.commit()


def test_admin_can_view_campaign_analytics(client: TestClient, db_session: Session, platform_factory, campaign_factory):
    plat = platform_factory("reddit")
    campaign = campaign_factory("AnalyticsCamp", [plat.id])
    seed_campaign_with_data(db_session, campaign, plat, matched=2, low=1, pending=3, over=2)
    # find admin creator user
    admin = db_session.query(User).filter(User.role == UserRole.ADMIN).first()
    assert admin is not None
    r = client.get(f"/api/v1/analytics/campaigns/{campaign.id}", headers={"Authorization": f"Bearer {admin.api_key}"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["campaign_id"] == campaign.id
    # totals: posts == sum of all created
    assert data["totals"]["posts"] == 2+1+2+3  # matched + low + over + pending
    # success_rate: (matched + low) / reconciled (total - pending)
    reconciled = (2+1+2)  # exclude pending 3
    success_rate_expected = (2+1)/reconciled
    assert abs(data["reconciliation"]["success_rate"] - round(success_rate_expected,4)) < 1e-6
    assert data["reconciliation"]["pending_reports"] == 3
    assert data["reconciliation"]["total_reconciled"] == reconciled
    # platform breakdown single platform
    assert len(data["platform_breakdown"]) == 1
    assert data["platform_breakdown"][0]["views"] == 100 * (2+1+2+3)
    # recent alerts includes overclaim alerts (2) limited to <=5
    assert len(data["recent_alerts"]) >= 2


def test_client_rbac_restricts_other_campaign(client: TestClient, db_session: Session, platform_factory, campaign_factory):
    plat = platform_factory("instagram")
    campaign = campaign_factory("ClientCamp", [plat.id])
    # create a second client + campaign
    second_campaign = campaign_factory("OtherCamp", [plat.id], new_client=True)
    # create client user for first campaign's client_id
    from app.models.db import Client as ClientModel
    client_model = db_session.query(ClientModel).filter(ClientModel.id == campaign.client_id).first()
    assert client_model is not None, "Expected client for campaign"
    client_user = User(
        name="ClientUser",
        email=f"c_{secrets.token_hex(4)}@ex.com",
        api_key=f"cli_{secrets.token_hex(8)}",
        role=UserRole.CLIENT,
        client_id=client_model.id,
    )
    db_session.add(client_user)
    db_session.commit()
    ok = client.get(f"/api/v1/analytics/campaigns/{campaign.id}", headers={"Authorization": f"Bearer {client_user.api_key}"})
    assert ok.status_code == 200
    forbidden = client.get(f"/api/v1/analytics/campaigns/{second_campaign.id}", headers={"Authorization": f"Bearer {client_user.api_key}"})
    assert forbidden.status_code == 403


def test_affiliate_forbidden(client: TestClient, db_session: Session, platform_factory, affiliate_factory, campaign_factory):
    plat = platform_factory("tiktok")
    campaign = campaign_factory("AffCamp", [plat.id])
    affiliate = affiliate_factory()
    r = client.get(f"/api/v1/analytics/campaigns/{campaign.id}", headers={"Authorization": f"Bearer {affiliate.api_key}"})
    assert r.status_code == 403


def test_campaign_not_found_returns_404(client: TestClient, db_session: Session):
    # create admin user to auth
    admin = User(name="AdminX", email="admin_x@example.com", api_key="adm_x", role=UserRole.ADMIN)
    db_session.add(admin)
    db_session.commit()
    r = client.get("/api/v1/analytics/campaigns/999999", headers={"Authorization": f"Bearer {admin.api_key}"})
    assert r.status_code == 404
