import os
import secrets
from fastapi.testclient import TestClient
import pytest

from app.config import BOT_INTERNAL_TOKEN as ORIGINAL_BOT_TOKEN  # just to ensure import path works
from app.models.db.affiliate_reports import SubmissionMethod
from app.models.db import Affiliate
from app.api.deps import get_submission_affiliate

# We rely on existing fixtures: client, platform_factory, affiliate_factory, campaign_factory, db_session (from conftest)

@pytest.fixture(autouse=True)
def _set_bot_token(monkeypatch):
    """Ensure BOT_INTERNAL_TOKEN is set both in environment and config module variable.

    Because app.config is imported early (via app.main in conftest), simply setting the
    env var after import won't update the already-bound module constant. We patch both.
    """
    import app.config as config  # local import to avoid circular issues
    monkeypatch.setenv("BOT_INTERNAL_TOKEN", "test_bot_internal_token")
    config.BOT_INTERNAL_TOKEN = "test_bot_internal_token"  # type: ignore
    yield


def _discord_link_affiliate(db_session, affiliate: Affiliate, discord_user_id: str):
    affiliate.discord_user_id = discord_user_id
    db_session.add(affiliate)
    db_session.commit()
    db_session.refresh(affiliate)


def test_bot_token_submission_success(client: TestClient, platform_factory, affiliate_factory, campaign_factory, db_session):
    reddit = platform_factory("reddit")
    affiliate = affiliate_factory(name="BotUser")
    _discord_link_affiliate(db_session, affiliate, discord_user_id="123456789012345678")
    campaign = campaign_factory("BotCampaign", [reddit.id])

    payload = {
        "campaign_id": campaign.id,
        "platform_id": reddit.id,
        "post_url": "https://reddit.com/r/test/xyz",
        "claimed_views": 42,
        "claimed_clicks": 5,
        "claimed_conversions": 1,
        "submission_method": SubmissionMethod.DISCORD.value
    }

    headers = {
        "Authorization": "Bot test_bot_internal_token",
        "X-Discord-User-ID": "123456789012345678"
    }
    r = client.post("/api/v1/submissions/", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body.get("success") is True
    assert body.get("data", {}).get("post_id") is not None


def test_bot_token_missing_discord_header(client: TestClient, platform_factory, affiliate_factory, campaign_factory, db_session):
    reddit = platform_factory("reddit")
    affiliate = affiliate_factory(name="BotUser2")
    _discord_link_affiliate(db_session, affiliate, discord_user_id="223456789012345678")
    campaign = campaign_factory("BotCampaign2", [reddit.id])

    payload = {
        "campaign_id": campaign.id,
        "platform_id": reddit.id,
        "post_url": "https://reddit.com/r/test/abc",
        "claimed_views": 10,
        "claimed_clicks": 1,
        "claimed_conversions": 0,
        "submission_method": SubmissionMethod.DISCORD.value
    }
    headers = {"Authorization": "Bot test_bot_internal_token"}
    r = client.post("/api/v1/submissions/", json=payload, headers=headers)
    assert r.status_code == 400, r.text


def test_bot_token_invalid_token(client: TestClient, platform_factory, affiliate_factory, campaign_factory, db_session):
    reddit = platform_factory("reddit")
    affiliate = affiliate_factory(name="BotUser3")
    _discord_link_affiliate(db_session, affiliate, discord_user_id="323456789012345678")
    campaign = campaign_factory("BotCampaign3", [reddit.id])

    payload = {
        "campaign_id": campaign.id,
        "platform_id": reddit.id,
        "post_url": "https://reddit.com/r/test/def",
        "claimed_views": 11,
        "claimed_clicks": 2,
        "claimed_conversions": 0,
        "submission_method": SubmissionMethod.DISCORD.value
    }
    headers = {
        "Authorization": "Bot wrong_token",
        "X-Discord-User-ID": "323456789012345678"
    }
    r = client.post("/api/v1/submissions/", json=payload, headers=headers)
    assert r.status_code == 401, r.text


def test_bot_token_unknown_discord_user(client: TestClient, platform_factory, affiliate_factory, campaign_factory):
    reddit = platform_factory("reddit")
    campaign = campaign_factory("BotCampaign4", [reddit.id])
    payload = {
        "campaign_id": campaign.id,
        "platform_id": reddit.id,
        "post_url": "https://reddit.com/r/test/ghi",
        "claimed_views": 12,
        "claimed_clicks": 1,
        "claimed_conversions": 0,
        "submission_method": SubmissionMethod.DISCORD.value
    }
    headers = {
        "Authorization": "Bot test_bot_internal_token",
        "X-Discord-User-ID": "999999999999999999"  # not linked
    }
    r = client.post("/api/v1/submissions/", json=payload, headers=headers)
    assert r.status_code == 404, r.text
