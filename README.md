# Affiliate Reconciliation Platform

End-to-end system for receiving affiliate-reported performance metrics, normalizing and verifying them against platform-sourced data, and surfacing discrepancies & trust signals—optimized for extensibility and rapid iteration.

## Table of Contents
- [1. High‑Level Overview](#1-high-level-overview)
- [2. Key Enhancements vs Original Brief](#2-key-enhancements-vs-original-brief)
- [3. Core Design Choices (Retained Summary)](#3-core-design-choices-retained-summary)
- [4. Minimal Architecture Snapshot](#4-minimal-architecture-snapshot)
- [5. Tech Stack](#5-tech-stack)
- [6. Quick Start](#6-quick-start)
- [7. Documentation Index](#7-documentation-index)
- [8. Current Capability Highlights](#8-current-capability-highlights)
- [9. Extending](#9-extending)
- [10. Roadmap Snapshot](#10-roadmap-snapshot)
- [11. Areas of Improvement](#11-areas-of-improvement)

## System Overview

Core responsibilities:
1. Accept affiliate submissions (API now; Discord-style ingestion planned but schema-ready).
2. Normalize links & enrich platform context (e.g., Reddit permalink normalization).
3. Generate or fetch platform truth metrics (mock adapters for now; real integration boundary preserved).
4. Reconcile claims vs truth & log discrepancies for auditability.
5. Maintain affiliate trust score as lightweight fraud/quality signal.
6. Expose structured, typed API responses for downstream dashboards / analytics.

Status: A lean but production-aligned core—no speculative abstractions, only primitives required by the brief + targeted integrity & governance improvements.

## 1. High‑Level Overview
This project implements an end‑to‑end reconciliation workflow:
* Accept submissions (API today; Discord ingestion schema-ready)
* Normalize links & identify platform context
* Fetch or simulate platform metrics via modular adapters (mock-first, real-ready)
* Reconcile claimed vs truth metrics, log outcomes, emit alerts, update trust scores
* Provide typed, documented API responses for downstream analytics / dashboards

The implementation is intentionally lean: only primitives needed for correctness, integrity, and extensibility—no speculative abstractions.

## 2. Key Enhancements vs Original Brief (Assumptions & Decisions)
These deliberate deviations / additions are explicitly documented for reviewer transparency:
| Area | Brief Expectation | Delivered Enhancement |
|------|-------------------|-----------------------|
| Reconciliation cadence | Periodic batch | Immediate + on‑demand via internal queue (faster feedback) |
| Platform integrations | Mock allowed | Unified adapter contract enabling drop‑in real clients |
| Evidence handling | Potential screenshot proofs | Removed image storage (attack surface + redundancy) using JSON evidence fallback |
| Data granularity | Campaign/date implied | Post‑centric model with historical snapshots |
| Inconsistency detection | Basic comparison | Discrepancy scaffolding + alert pipeline + trust scoring |
| Security | Basic auth | API key + role-based admin guard (RBAC scaffold) |
| Observability | Unspecified | Structured logging, metrics hooks, circuit breaker, backoff, priority queue |

See `affiliate-reconciliation-backend/docs/ROADMAP.md` for what is planned next.

## 3. Core Design Choices (Retained Summary)
* **Mock‑first strategy** – Accelerates iteration; real APIs can replace metric generators behind existing interfaces.
* **Post‑centric schema** – Enables precise duplicate prevention and longitudinal reconciliation.
* **Append‑only reports + immutable logs** – Preserves audit history.
* **Trust scoring** – Lightweight fraud & quality signal (`accurate_submissions / total_submissions`).
* **Immediate reconciliation** – Queue-based trigger instead of cron; lowers detection latency.
* **Enum hardening** – Reduces typo risk (roles, statuses, submission methods).
* **Removed binary proofs** – Less storage, bandwidth, and security overhead.
* **Circuit breaker & backoff utilities** – Resilience primitives for future real API calls.
* **Structured JSON logging** – Correlation IDs + business context for observability.

Deep dives for each topic live in the docs directory (links below).

## 4. Minimal Architecture Snapshot
```
Clients → FastAPI Layer → Domain Services (Submissions • Integrations • Reconciliation • Trust/Alerts)
          ↓
        Persistence (SQLite dev / PostgreSQL target) + Queue + Structured Logging
```

## 5. Tech Stack
* Python 3.11+
* FastAPI + Pydantic (v2 style schemas)
* SQLAlchemy ORM
* In‑process priority job queue + worker
* Structured logging utilities (JSON)
* Poetry for dependency & environment management

## 6. Quick Start
```bash
git clone <repo-url>
cd affiliate-reconciliation-backend
poetry install
poetry run pytest -q      # optional verification
poetry run uvicorn app.main:app --reload
```
API Docs: http://localhost:8000/docs (Swagger) • http://localhost:8000/redoc

Optional `.env` (defaults work):
```bash
DATABASE_URL=sqlite:///./test.db
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
INTEGRATIONS_RANDOM_SEED=12345
MOCK_FAILURE_RATE=0.05
```

### 6.1 Docker Quick Start
Run the full stack (API + Redis + Postgres + worker) with Docker. Requires Docker Desktop.

```bash
# From repo root (same level as docker-compose.yml)
cd affiliate-reconciliation-backend

# 1. Copy or create an .env (optional – defaults are fine)
copy .env.example .env  # Windows (PowerShell: cp .env.example .env)

# 2. Start all services (builds images on first run)
docker compose up -d --build

# 3. View logs
docker compose logs -f app

# 4. Run tests inside a disposable container (optional)
docker compose run --rm app pytest -q

# 5. Stop services
docker compose down
```

Service endpoints:
* API: http://localhost:8000
* Docs: http://localhost:8000/docs
* Postgres: localhost:5432 (user/pass: postgres / postgres unless overridden)
* Redis: localhost:6379

Environment tweaks (edit `.env`):
* Switch to Redis queue: `QUEUE_SETTINGS_USE_REDIS=true`
* Use Postgres DB (compose default): `DATABASE_URL=postgresql://postgres:postgres@db/affiliate_reconciliation`
* Persist logs locally: mounted `./logs` directory

Common Docker commands:
```bash
docker compose ps
docker compose logs -f worker
docker compose exec app bash
docker compose down -v   # remove volumes (DB + Redis data)
```

Minimal production-style image build (API only):
```bash
docker build -t affiliate-platform:latest ./affiliate-reconciliation-backend
docker run -p 8000:8000 --env-file ./affiliate-reconciliation-backend/.env affiliate-platform:latest
```

## 7. Documentation Index
| Topic | Link |
|-------|------|
| Architecture Overview | [ARCHITECTURE_OVERVIEW.md](affiliate-reconciliation-backend/docs/ARCHITECTURE_OVERVIEW.md) |
| Data Model & Integrity | [DATA_MODEL.md](affiliate-reconciliation-backend/docs/DATA_MODEL.md) |
| Reconciliation Engine | [RECONCILIATION_ENGINE.md](affiliate-reconciliation-backend/docs/RECONCILIATION_ENGINE.md) |
| Queue & Worker | [QUEUE_AND_WORKER.md](affiliate-reconciliation-backend/docs/QUEUE_AND_WORKER.md) |
| Alerting & Trust Scoring | [ALERTING_AND_TRUST.md](affiliate-reconciliation-backend/docs/ALERTING_AND_TRUST.md) |
| Platform Integrations | [INTEGRATIONS.md](affiliate-reconciliation-backend/docs/INTEGRATIONS.md) |
| API Reference | [API_REFERENCE.md](affiliate-reconciliation-backend/docs/API_REFERENCE.md) |
| Configuration Reference | [CONFIGURATION.md](affiliate-reconciliation-backend/docs/CONFIGURATION.md) |
| Setup / Deployment | [SETUP_GUIDE.md](affiliate-reconciliation-backend/docs/SETUP_GUIDE.md) |
| Data Flow Examples | [DATA_FLOW_EXAMPLES.md](affiliate-reconciliation-backend/docs/DATA_FLOW_EXAMPLES.md) |
| Testing Strategy | [TESTING_STRATEGY.md](affiliate-reconciliation-backend/docs/TESTING_STRATEGY.md) |
| Roadmap | [ROADMAP.md](affiliate-reconciliation-backend/docs/ROADMAP.md) |

## 8. Current Capability Highlights
| Capability | Status |
|------------|--------|
| Multi-platform mock adapters (Instagram, Reddit, TikTok, X, YouTube) | ✅ |
| Priority job queue + worker threads | ✅ |
| Redis-backed queue with in-memory fallback | ✅ |
| Reconciliation engine + discrepancy detection | ✅ |
| Trust scoring updates per reconciliation | ✅ |
| Alert scaffolding (threshold-driven notifications) | ✅ |
| Circuit breaker & backoff utilities | ✅ |
| Structured JSON logging with correlation IDs | ✅ |
| RBAC (admin campaign creation, role-based access) | ✅ |
| Observability extensions (metrics, webhooks) | 🚧 Planned |

## 9. Extending
* New platform: add `app/integrations/<platform>.py` implementing fetch + unify → register.
* Real API: swap mock generator with HTTP client, preserve output schema.
* Advanced reconciliation: implement threshold matrix + alert escalation logic.

## 10. Roadmap Snapshot
See full list in `docs/ROADMAP.md`. Near-term priorities: PostgreSQL migration, Prometheus metrics, webhook/Slack alerting, richer trust weighting.

## 11. Areas of Improvement

### 1. Enhanced Logging Infrastructure
**Replace current logging with MongoDB-backed solution**
- Store structured logs in MongoDB for better querying and analytics
- Enable complex log aggregations and historical analysis
- Support for log retention policies and archival
- Real-time log monitoring and alerting capabilities

### 2. Affiliate API Key Integration
**Request platform API keys from affiliates for enhanced data access**
- Allow affiliates to provide their own API keys for supported platforms
- Access detailed private insights not available through public APIs
- Fetch granular performance metrics (impressions, engagement rates, demographics)
- Enable real-time data synchronization instead of periodic polling
- Implement secure key storage with encryption and access controls

### 3. Stale Data Detection & Alerts
**Monitor and alert on posts with outdated metrics**
- Track last update timestamps for all posts
- Implement configurable thresholds for "stale" data detection
- Generate alerts when posts haven't been updated within expected windows
- Consider platform-specific update frequencies (e.g., Reddit vs Instagram)
- Prevent reconciliation of potentially outdated platform data

---


