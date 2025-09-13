from fastapi.testclient import TestClient
from app.models.db import Platform
from app.models.db.affiliate_reports import SubmissionMethod


def test_full_affiliate_submission_flow(client, db_session, platform_factory, affiliate_factory, campaign_factory):
    # Seed platforms
    reddit = platform_factory("reddit")
    instagram = platform_factory("instagram")

    # Create affiliate via API (tests POST /affiliates)
    payload = {"name": "Alpha Influencer", "email": "alpha@example.com"}
    r = client.post("/api/v1/affiliates/", json=payload)
    assert r.status_code == 201, r.text
    affiliate_data = r.json()
    assert affiliate_data["api_key"].startswith("aff_")

    api_key = affiliate_data["api_key"]
    auth = {"Authorization": f"Bearer {api_key}"}

    # Create campaign directly using DB (no endpoint for platforms create so we also use DB for campaign)
    campaign = campaign_factory("Launch Campaign", [reddit.id, instagram.id])

    # List platforms (GET /platforms)
    r = client.get("/api/v1/platforms/")
    assert r.status_code == 200
    assert any(p["name"] == "reddit" for p in r.json())

    # Submit new post (POST /submissions)
    submission_payload = {
        "campaign_id": campaign.id,
        "platform_id": reddit.id,
        "post_url": "https://reddit.com/r/test/abc123",
        "title": "Great Product!",
        "claimed_views": 1000,
        "claimed_clicks": 50,
        "claimed_conversions": 5,
        "evidence_data": {"screenshots": ["http://img.test/1.png"]},
        "submission_method": SubmissionMethod.API.value
    }
    r = client.post("/api/v1/submissions/", json=submission_payload, headers=auth)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["success"] is True
    post_id = data["data"]["post_id"]

    # Update metrics (PUT /submissions/{post_id}/metrics)
    update_payload = submission_payload | {"claimed_views": 1500, "claimed_clicks": 70, "claimed_conversions": 7}
    r = client.put(f"/api/v1/submissions/{post_id}/metrics", json=update_payload, headers=auth)
    assert r.status_code == 200, r.text

    # Fetch history (GET /submissions/history)
    r = client.get("/api/v1/submissions/history", headers=auth)
    assert r.status_code == 200
    history = r.json()
    assert len(history) == 1
    assert history[0]["id"] == post_id

    # Metrics history (GET /submissions/{post_id}/metrics)
    r = client.get(f"/api/v1/submissions/{post_id}/metrics", headers=auth)
    assert r.status_code == 200
    metrics_history = r.json()
    assert len(metrics_history) == 2  # original + update
    assert metrics_history[-1]["claimed_views"] == 1500

    # Trigger reconciliation (POST /reconciliation/run)
    r = client.post("/api/v1/reconciliation/run", json={"post_id": post_id, "force_reprocess": False})
    assert r.status_code == 200
    assert r.json()["success"] is True

    # Reconciliation results (GET /reconciliation/results)
    r = client.get("/api/v1/reconciliation/results")
    assert r.status_code == 200

    # Alerts list empty (GET /alerts)
    r = client.get("/api/v1/alerts/")
    assert r.status_code == 200
    assert r.json() == []
