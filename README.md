# Affiliate Reconciliation Platform

End-to-end system for receiving affiliate-reported performance metrics, normalizing and verifying them against platform-sourced data, and surfacing discrepancies & trust signals—optimized for extensibility and rapid iteration.

## Table of Contents
- [System Overview](#system-overview)
- [Why Mock Platforms](#why-mock-platforms)
- [Why We Removed Image Proofs](#why-we-removed-image-proofs)
- [Architecture](#architecture)
- [Data Model & Integrity](#data-model--integrity)
- [Reconciliation Lifecycle](#reconciliation-lifecycle)
- [Enhancements vs Brief](#enhancements-vs-brief)
- [Assumptions & Design Choices](#assumptions--design-choices)
- [RBAC & Security](#rbac--security)
- [API Surface (Implemented)](#api-surface-implemented)
- [Running Locally](#running-locally)
- [Extending the System](#extending-the-system)
- [Future Opportunities](#future-opportunities)

## System Overview

Core responsibilities:
1. Accept affiliate submissions (API now; Discord-style ingestion planned but schema-ready).
2. Normalize links & enrich platform context (e.g., Reddit permalink normalization).
3. Generate or fetch platform truth metrics (mock adapters for now; real integration boundary preserved).
4. Reconcile claims vs truth & log discrepancies for auditability.
5. Maintain affiliate trust score as lightweight fraud/quality signal.
6. Expose structured, typed API responses for downstream dashboards / analytics.

Status: A lean but production-aligned core—no speculative abstractions, only primitives required by the brief + targeted integrity & governance improvements.

# Affiliate Reconciliation Platform

Fast, extensible system for ingesting affiliate‑reported performance metrics, reconciling them against platform truth, surfacing discrepancies, and tracking affiliate trust.

</div>

## 1. High‑Level Overview
This project implements an end‑to‑end reconciliation workflow:
* Accept submissions (API today; Discord ingestion schema-ready)
* Normalize links & identify platform context
* Fetch or simulate platform metrics via modular adapters (mock-first, real-ready)
* Reconcile claimed vs truth metrics, log outcomes, emit alerts, update trust scores
* Provide typed, documented API responses for downstream analytics / dashboards

The implementation is intentionally lean: only primitives needed for correctness, integrity, and extensibility—no speculative abstractions.

## 2. Key Enhancements vs Original Brief
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

## 7. Documentation Index
| Topic | File |
|-------|------|
| Architecture Overview | `affiliate-reconciliation-backend/docs/ARCHITECTURE_OVERVIEW.md` |
| Data Model & Integrity | `affiliate-reconciliation-backend/docs/DATA_MODEL.md` |
| Reconciliation Engine | `affiliate-reconciliation-backend/docs/RECONCILIATION_ENGINE.md` |
| Queue & Worker | `affiliate-reconciliation-backend/docs/QUEUE_AND_WORKER.md` |
| Alerting & Trust Scoring | `affiliate-reconciliation-backend/docs/ALERTING_AND_TRUST.md` |
| Platform Integrations | `affiliate-reconciliation-backend/docs/INTEGRATIONS.md` |
| API Reference | `affiliate-reconciliation-backend/docs/API_REFERENCE.md` |
| Configuration Reference | `affiliate-reconciliation-backend/docs/CONFIGURATION.md` |
| Setup / Deployment | `affiliate-reconciliation-backend/docs/SETUP_GUIDE.md` |
| Data Flow Examples | `affiliate-reconciliation-backend/docs/DATA_FLOW_EXAMPLES.md` |
| Testing Strategy | `affiliate-reconciliation-backend/docs/TESTING_STRATEGY.md` |
| Roadmap | `affiliate-reconciliation-backend/docs/ROADMAP.md` |

## 8. Current Capability Highlights
| Capability | Status |
|------------|--------|
| Multi-platform mock adapters | ✅ |
| Priority job queue + worker | ✅ |
| Reconciliation + discrepancy logging | ✅ |
| Trust scoring updates per reconciliation | ✅ |
| Alert scaffolding (threshold-driven) | ✅ |
| Circuit breaker & backoff utilities | ✅ |
| Structured JSON logging | ✅ |
| RBAC (admin campaign creation) | ✅ |
| Observability extensions (metrics, webhooks) | 🚧 Planned |

## 9. Extending
* New platform: add `app/integrations/<platform>.py` implementing fetch + unify → register.
* Real API: swap mock generator with HTTP client, preserve output schema.
* Advanced reconciliation: implement threshold matrix + alert escalation logic.

## 10. Roadmap Snapshot
See full list in `docs/ROADMAP.md`. Near-term priorities: production-grade external queue (Redis/SQS), PostgreSQL migration, Prometheus metrics, webhook/Slack alerting, richer trust weighting.

---
