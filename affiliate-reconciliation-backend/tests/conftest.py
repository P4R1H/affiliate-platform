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
    Platform, Campaign, User, Post, ReconciliationLog, Alert,
    # Import modules that define back_populates targets to ensure mapper config
)
from app.models.db.enums import CampaignStatus, UserRole
from app.jobs.queue import PriorityDelayQueue
from app.jobs.worker_reconciliation import ReconciliationWorker
from app.utils.circuit_breaker import GLOBAL_CIRCUIT_BREAKER

@pytest.fixture(scope="session", autouse=True)
def reconciliation_queue(create_test_db):  # depend on DB creation
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

@pytest.fixture(autouse=True)
def _isolate_test_state(reconciliation_queue, db_session):  # type: ignore[unused-argument]
        """Ensure per-test isolation for in-memory single-process components.

        Resets:
            - In-memory circuit breaker (failure counters / state) to avoid cross-test spill.
            - In-memory queue contents (purge) so no leftover scheduled retries inflate later tests.
        """
        # Pre-test cleanup (in case prior test aborted mid-way)
        reconciliation_queue.purge()
        GLOBAL_CIRCUIT_BREAKER._states.clear()  # type: ignore[attr-defined]
        yield
        # Post-test cleanup
        reconciliation_queue.purge()
        GLOBAL_CIRCUIT_BREAKER._states.clear()  # type: ignore[attr-defined]

# Use file-based SQLite for thread-safe multi-connection access (worker thread + test thread)
# In-memory with StaticPool (single connection) caused cross-thread flush anomalies.
SQLALCHEMY_TEST_URL = "sqlite+pysqlite:///./test_worker.db"
engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Critical: ensure background worker threads use the in-memory test DB ---
# The worker module imported SessionLocal at import time (binding to file-based DB).
# We rebind both the app.database module attribute and the worker module attribute
# to our in-memory TestingSessionLocal so reconciliations performed in the worker
# see the same data created via API requests in tests.
import app.database as _app_database  # noqa: E402
_app_database.SessionLocal = TestingSessionLocal  # type: ignore
import app.jobs.worker_reconciliation as _worker_mod  # noqa: E402
_worker_mod.SessionLocal = TestingSessionLocal  # type: ignore

@pytest.fixture(scope="session", autouse=True)
def create_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    try:
        os.remove("test_worker.db")
    except OSError:
        pass

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
        while db_session.query(User).filter_by(name=name).first():
            attempt += 1
            name = f"{name}-{attempt}-{secrets.token_hex(1)}"
        a = User(name=name, email=email, api_key=f"aff_{secrets.token_hex(12)}", role=UserRole.AFFILIATE)
        db_session.add(a)
        db_session.commit()
        db_session.refresh(a)
        return a
    return _create

@pytest.fixture()
def campaign_factory(db_session):
    def _create(name: str, platform_ids: list[int], *, new_client: bool = False):
        from datetime import date
        from app.models.db import Platform, Campaign, Client, User
        from app.models.db.enums import UserRole
        import secrets
        
        # Create or reuse client
        client = None
        if not new_client:
            client = db_session.query(Client).first()
        if client is None:
            client = Client(name=f"Test Client {secrets.token_hex(2)}")
            db_session.add(client)
            db_session.flush()
        
        # Get or create an admin user to be the campaign creator
        admin_user = db_session.query(User).filter(User.role == UserRole.ADMIN).first()
        if not admin_user:
            admin_user = User(
                name=f"Admin User {secrets.token_hex(2)}",
                email=f"admin_{secrets.token_hex(4)}@example.com",
                role=UserRole.ADMIN,
                api_key=f"admin_key_{secrets.token_hex(8)}"
            )
            db_session.add(admin_user)
            db_session.flush()
        
        platforms = db_session.query(Platform).filter(Platform.id.in_(platform_ids)).all()
        campaign = Campaign(
            name=name, 
            client_id=client.id, 
            created_by=admin_user.id,
            start_date=date(2025, 1, 1), 
            status=CampaignStatus.ACTIVE
        )
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

