from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.db import Affiliate
from app.models.db.enums import UserRole, CampaignStatus
import secrets


def test_duplicate_affiliate_email_conflict(client: TestClient):
    unique_email = f"dup_{secrets.token_hex(4)}@example.com"
    payload = {"name": "CreatorOne", "email": unique_email}
    first = client.post("/api/v1/affiliates/", json=payload)
    assert first.status_code == 201, first.text
    second = client.post("/api/v1/affiliates/", json=payload)
    assert second.status_code == 409, second.text


def test_campaign_creation_requires_admin(client: TestClient, db_session: Session, platform_factory):
    # Create non-admin affiliate
    r = client.post("/api/v1/affiliates/", json={"name": "RegularUser", "email": "regu@example.com"})
    assert r.status_code == 201
    api_key = r.json()["api_key"]
    headers = {"Authorization": f"Bearer {api_key}"}

    # Seed platform
    plat = platform_factory("reddit")

    # Attempt campaign creation without admin role
    campaign_payload = {
        "name": "Test Campaign Enum",
        "advertiser_name": "AdvCo",
        "start_date": "2025-01-01",
        "platform_ids": [plat.id]
    }
    r_fail = client.post("/api/v1/campaigns/", json=campaign_payload, headers=headers)
    assert r_fail.status_code == 403

    # Promote affiliate to admin directly in DB
    aff = db_session.query(Affiliate).filter_by(email="regu@example.com").first()
    assert aff is not None
    aff.role = UserRole.ADMIN
    db_session.commit()

    # Retry with admin role
    r_ok = client.post("/api/v1/campaigns/", json=campaign_payload, headers=headers)
    assert r_ok.status_code == 201, r_ok.text
    data = r_ok.json()
    assert data["status"] == CampaignStatus.ACTIVE


def test_campaign_creation_unauthenticated_rejected(client: TestClient, platform_factory):
    plat = platform_factory("instagram")
    campaign_payload = {
        "name": "NoAuth Campaign",
        "advertiser_name": "BrandX",
        "start_date": "2025-02-01",
        "platform_ids": [plat.id]
    }
    # No Authorization header supplied
    r = client.post("/api/v1/campaigns/", json=campaign_payload)
    # Expect 401 (no bearer token) rather than 403 (role) because authentication fails first
    assert r.status_code in (401, 403)