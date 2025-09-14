import time
import pytest
from fastapi.testclient import TestClient
from app.config import RATE_LIMIT_SETTINGS

# We use a very small window for a synthetic category override in tests by monkeypatching settings if needed

@pytest.fixture()
def fast_limits(monkeypatch):
    # Shrink windows to speed up reset tests
    RATE_LIMIT_SETTINGS['default']['limit'] = 5  # type: ignore[index]
    RATE_LIMIT_SETTINGS['default']['window_seconds'] = 2  # 2 second window
    RATE_LIMIT_SETTINGS['submission']['limit'] = 3  # type: ignore[index]
    RATE_LIMIT_SETTINGS['submission']['window_seconds'] = 2  # type: ignore[index]
    yield


def _submission_payload(platform_id: int, campaign_id: int, post_url: str):
    return {
        "platform_id": platform_id,
        "campaign_id": campaign_id,
        "post_url": post_url,
        "claimed_views": 10,
        "claimed_clicks": 5,
        "claimed_conversions": 1,
    }


def test_generic_rate_limit_enforced(client: TestClient, platform_factory, affiliate_factory, campaign_factory, fast_limits, db_session):
    # Setup platform + campaign
    p = platform_factory("reddit")
    c = campaign_factory("Camp RL", [p.id])
    affiliate = affiliate_factory()
    headers = {"Authorization": f"Bearer {affiliate.api_key}"}

    # Hit root (falls under default category) within limit
    for i in range(5):
        r = client.get("/", headers=headers)
        assert r.status_code == 200
        assert r.headers.get("X-RateLimit-Limit") == "5"
        remaining = int(r.headers.get("X-RateLimit-Remaining"))
        assert remaining == 5 - (i + 1)

    # Next request should exceed
    r = client.get("/", headers=headers)
    assert r.status_code == 429
    assert r.json()["message"].startswith("Rate limit exceeded")
    assert r.headers.get("X-RateLimit-Remaining") == "0"


def test_submission_category_limits(client: TestClient, platform_factory, affiliate_factory, campaign_factory, fast_limits):
    p = platform_factory("instagram")
    c = campaign_factory("Camp SM", [p.id])
    affiliate = affiliate_factory()
    headers = {"Authorization": f"Bearer {affiliate.api_key}"}

    # 3 allowed
    for i in range(3):
        r = client.post("/api/v1/submissions/", json=_submission_payload(p.id, c.id, f"https://example.com/post/{i}"), headers=headers)
        # Accept either success or domain specific errors unrelated to rate limit; just assert not 429
        assert r.status_code != 429
    # 4th hits 429
    r = client.post("/api/v1/submissions/", json=_submission_payload(p.id, c.id, "https://example.com/post/x"), headers=headers)
    assert r.status_code == 429
    assert r.json()["category"] == "submission"


def test_window_reset_allows_requests_again(client: TestClient, platform_factory, affiliate_factory, campaign_factory, fast_limits):
    p = platform_factory("tiktok")
    c = campaign_factory("Camp TT", [p.id])
    affiliate = affiliate_factory()
    headers = {"Authorization": f"Bearer {affiliate.api_key}"}

    for _ in range(5):
        assert client.get("/", headers=headers).status_code in (200,)
    assert client.get("/", headers=headers).status_code == 429

    # Wait for window to reset (2s + small buffer)
    time.sleep(2.2)
    r = client.get("/", headers=headers)
    assert r.status_code == 200
    assert r.headers.get("X-RateLimit-Remaining") == "4"  # after 1st of new window


def test_reconciliation_trigger_category(client: TestClient, platform_factory, affiliate_factory, campaign_factory, fast_limits, db_session):
    # Need a client or admin user for trigger. Use campaign_factory to create admin.
    p = platform_factory("youtube")
    c = campaign_factory("Camp YT", [p.id])
    # Get admin user created by campaign_factory
    from app.models.db import User
    from app.models.db.enums import UserRole
    admin_user = db_session.query(User).filter(User.role == UserRole.ADMIN).first()
    assert admin_user is not None
    headers = {"Authorization": f"Bearer {admin_user.api_key}"}

    # Set recon trigger limit tiny
    RATE_LIMIT_SETTINGS['recon_trigger']['limit'] = 2  # type: ignore[index]
    RATE_LIMIT_SETTINGS['recon_trigger']['window_seconds'] = 2  # type: ignore[index]

    payload = {"post_id": None, "force_reprocess": False}
    for _ in range(2):
        r = client.post("/api/v1/reconciliation/run", json=payload, headers=headers)
        assert r.status_code != 429
    r = client.post("/api/v1/reconciliation/run", json=payload, headers=headers)
    assert r.status_code == 429
    assert r.json()["category"] == "recon_trigger"


def test_rate_limit_headers_exist_for_public_route(client: TestClient, fast_limits):
    # No auth header -> public key bucket
    r = client.get("/health")
    assert r.status_code == 200
    assert "X-RateLimit-Limit" in r.headers
    assert "X-RateLimit-Remaining" in r.headers
    assert "X-RateLimit-Reset" in r.headers
