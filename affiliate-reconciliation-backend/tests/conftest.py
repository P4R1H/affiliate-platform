import os
import secrets
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure project root on sys.path so 'app' package resolves when running via poetry
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.main import app  # type: ignore
from app.database import Base  # type: ignore
from app.api import deps  # type: ignore
"""Pytest fixtures and factories.

Important: SQLAlchemy relationship configuration requires all model modules to be imported
before Base.metadata.create_all(), otherwise back_populates targets might not exist yet.
"""
from app.models.db import (
    Platform, Campaign, Affiliate, Post, AffiliateReport, ReconciliationLog, Alert,
    # Import modules that define back_populates targets to ensure mapper config
)
from app.models.db import platforms, campaigns, affiliates, posts, affiliate_reports, platform_reports, reconciliation_logs, alerts  # noqa: F401
from app.models.db.enums import CampaignStatus, UserRole
from app.jobs.queue import PriorityDelayQueue
from app.jobs.worker_reconciliation import ReconciliationWorker

@pytest.fixture(scope="session", autouse=True)
def reconciliation_queue():
    """Provide a queue instance on app.state for endpoints during tests.

    The production app sets this up in lifespan. Tests bypass lifespan so we replicate here.
    """
    queue = PriorityDelayQueue()
    app.state.reconciliation_queue = queue  # type: ignore[attr-defined]
    # Start worker thread (daemon) for tests; simplified without shutdown join.
    worker = ReconciliationWorker(queue)
    worker.start()
    yield queue
    queue.shutdown()

# Use in-memory SQLite for isolation & speed
SQLALCHEMY_TEST_URL = "sqlite+pysqlite:///:memory:"  # shared memory per process
engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def create_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture()
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

# Override dependency
def _override_get_db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

app.dependency_overrides[deps.get_db] = _override_get_db

@pytest.fixture()
def client():
    return TestClient(app)

# ---------- Data factory helpers ----------

@pytest.fixture()
def platform_factory(db_session):
    created = []
    def _create(name: str):
        existing = db_session.query(Platform).filter_by(name=name).first()
        if existing:
            return existing
        p = Platform(name=name, api_base_url=f"https://api.{name}.mock")
        db_session.add(p)
        db_session.commit()
        db_session.refresh(p)
        created.append(p)
        return p
    return _create

@pytest.fixture()
def affiliate_factory(db_session):
    def _create(name: str = "Test Affiliate", email: str | None = None):
        # Ensure uniqueness for default name to avoid IntegrityError between tests
        if name == "Test Affiliate":
            name = f"Test Affiliate {secrets.token_hex(2)}"
        if email is None:
            email = f"{secrets.token_hex(4)}@example.com"
        # If collision occurs (rare), retry with new suffix
        attempt = 0
        while db_session.query(Affiliate).filter_by(name=name).first():
            attempt += 1
            name = f"{name}-{attempt}-{secrets.token_hex(1)}"
        a = Affiliate(name=name, email=email, api_key=f"aff_{secrets.token_hex(12)}")
        db_session.add(a)
        db_session.commit()
        db_session.refresh(a)
        return a
    return _create

@pytest.fixture()
def campaign_factory(db_session):
    def _create(name: str, platform_ids: list[int]):
        from datetime import date
        from app.models.db import Platform, Campaign
        platforms = db_session.query(Platform).filter(Platform.id.in_(platform_ids)).all()
        campaign = Campaign(name=name, advertiser_name="Acme", start_date=date(2025, 1, 1), status=CampaignStatus.ACTIVE)
        campaign.platforms = platforms
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)
        return campaign
    return _create

@pytest.fixture()
def auth_header(affiliate_factory):
    affiliate = affiliate_factory()
    return {"Authorization": f"Bearer {affiliate.api_key}"}, affiliate

