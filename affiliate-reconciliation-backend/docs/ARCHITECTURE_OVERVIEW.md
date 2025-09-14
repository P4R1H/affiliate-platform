# Architecture Overview

## 1. Purpose & Scope
This document orients a new engineer in under 15 minutes to the## 7. Status & State Model (Simplified)
| Status | Terminal? | Trust Event? | Retry Eligible | Alert Potential |
|--------|-----------|--------------|---------------|-----------------|
| MATCHED | Yes | PERFECT_MATCH | No | No |
| DISCREPANCY_LOW | Yes | MINOR_DISCREPANCY | No | No |
| DISCREPANCY_MEDIUM | Yes | MEDIUM_DISCREPANCY | No | No |
| DISCREPANCY_HIGH | Yes | HIGH_DISCREPANCY | No | High Discrepancy Alert |
| AFFILIATE_OVERCLAIMED | Yes | OVERCLAIM | No | Overclaim Alert |
| INCOMPLETE_PLATFORM_DATA | No (1 extra attempt) | None | Yes | No |
| MISSING_PLATFORM_DATA | No (until max/window) | None | Yes | Missing Data Alert |
| UNVERIFIABLE | Yes | None | No | Data Quality Alert |
| SKIPPED_SUSPENDED | Yes | None | No | System Health Alert |s domain model, moving parts, and the life of a submission from API ingest to reconciliation outcome, trust score shifts, and alert emission.

## 2. High-Level Goals
| Goal | Why It Matters | Realization |
|------|----------------|-------------|
| Accurate affiliate claim validation | Prevent fraud & data quality drift | Reconciliation engine + classification tiers |
| Fast ingestion, deferred heavy work | Keep API latency low | Async queue + worker thread |
| Explainable risk scoring | Transparent enforcement & moderation | Trust events with config deltas |
| Actionable alerting | Operational & fraud triage | Structured alert types & categories |
| Resilient to platform issues | Avoid thrashing on outages | Circuit breaker + retry scheduling |
| Incremental enhancement path | Rapid iteration | Config-driven thresholds & modular services |

## 3. Component Map (Text Diagram)
```
[ Client / Affiliate ]
        |
        v (REST JSON + Bearer Auth)
+-----------------------+
| FastAPI API Layer     |  <-- auth, validation, persistence of AffiliateReport
| (lifespan management) |
+-----------+-----------+
            | enqueue (reconciliation job)
            v
      +-------------+            +--------------------+
      | Priority    |  pop job   | Reconciliation     |
      | Delay Queue +----------->| Worker Thread      |
      +------+------+            +---------+----------+
             ^                              |
             | (scheduled retry)            | run_reconciliation(report_id)
             v                              v
        +----+------------------------------+-----------------------------+
        | Reconciliation Engine: fetch -> classify -> trust -> alert -> log|
        +----+-----------------+-------------------+----------------------+ 
             |                 |                   |
             v                 v                   v
       PlatformFetcher   Trust Scoring       Alerting Service
             |                 |                   |
             v (adapters)      |                   |
     app.integrations.*        |                   |
             |                 |                   |
             +-----------------+-------------------+
                               |
                               v
                     SQLAlchemy ORM / SQLite (tests) | PostgreSQL (prod)
```
```
[ Client / Affiliate ]
        |
        v (REST JSON)
+-----------------------+
| FastAPI API Layer     |  <-- auth, validation, persistence of AffiliateReport
| (lifespan management) |
+-----------+-----------+
            | enqueue (reconciliation job)
            v
      +-------------+            +--------------------+
      | Priority    |  pop job   | Reconciliation     |
      | Delay Queue +----------->| Worker Thread      |
      +------+------+            +---------+----------+
             ^                              |
             | (scheduled retry)            | run_reconciliation(report_id)
             |                              v
        +----+------------------------------+-----------------------------+
        | Reconciliation Engine: fetch -> classify -> trust -> alert -> log|
        +----+-----------------+-------------------+----------------------+ 
             |                 |                   |
             v                 v                   v
       PlatformFetcher   Trust Scoring       Alerting Service
             |                 |                   |
             v (adapters)      |                   |
     app.integrations.*        |                   |
             |                 |                   |
             +-----------------+-------------------+
                               |
                               v
                     SQLAlchemy ORM / SQLite (tests)
```

## 4. Request → Outcome Sequence
1. Affiliate POSTs `/submissions/` with claimed metrics.
2. API validates campaign ↔ platform membership, post uniqueness, stores `Post`, `AffiliateReport`.
3. API enqueues reconciliation job referencing the new `AffiliateReport.id`.
4. Worker dequeues job, invokes `run_reconciliation`.
5. Engine ensures `ReconciliationLog` baseline row.
6. `PlatformFetcher` fetches authoritative metrics with circuit breaker + retry-in-attempt.
7. `classify()` assigns status + discrepancy level + trust event.
8. Trust scoring applies delta (bounded 0–1) & updates affiliate.
9. Optional `PlatformReport` row persisted (one per attempt when any metric present).
10. Retry scheduling logic sets `scheduled_retry_at` for transient states (missing/incomplete).
11. `maybe_create_alert` emits alert if rules fire.
12. Transaction commits; worker loop completes.
13. Future scheduled retry enqueued externally (future enhancement) or by scheduler.

## 5. Data Ownership & Single Source of Truth
| Entity | Source of Truth | Lifecycle |
|--------|-----------------|-----------|
| AffiliateReport | API submission | Immutable after creation (except reconciliation linkage) |
| ReconciliationLog | Engine | Updated per attempt (attempt_count, status, diffs, retry) |
| PlatformReport | Engine | Append-only snapshot per attempt (auditable) |
| Alert | Alerting service | Created once per log (no mutation yet) |
| Trust Score | Affiliate row | Mutated only by trust events inside reconciliation txn |

## 6. Design Rationale Highlights
- Single `ReconciliationLog` vs multiple logs: simplifies querying "latest status" while platform snapshots remain historical via `PlatformReport` rows.
- Append-only `PlatformReport`: auditability of platform metric evolution and growth allowance adjustments.
- Classification separated from engine orchestration for testability and future ML replacement.
- Circuit breaker is in-memory MVP: prevents hammering a failing integration before we invest in distributed state.
- Priority + delay queue implemented with two heaps: avoids starvation from far-future high-priority jobs.
- Trust deltas stored on log (optional field) for downstream analytics of which reconciliation changed trust.

## 7. Status & State Model (Simplified)
| Status | Terminal? | Trust Event? | Retry Eligible | Alert Potential |
|--------|-----------|--------------|---------------|-----------------|
| MATCHED | Yes (if no retry) | PERFECT_MATCH | No | No |
| DISCREPANCY_LOW | Yes | MINOR_DISCREPANCY | No | No |
| DISCREPANCY_MEDIUM | Yes | MEDIUM_DISCREPANCY | No | No |
| DISCREPANCY_HIGH | Yes | HIGH_DISCREPANCY | No | High Discrepancy Alert |
| AFFILIATE_OVERCLAIMED | Yes | OVERCLAIM | No | Overclaim Alert |
| INCOMPLETE_PLATFORM_DATA | No (1 extra attempt) | None | Yes | No |
| MISSING_PLATFORM_DATA | No (until max/window) | None | Yes | Missing Data Alert (terminal without retry) |

## 8. Failure Modes & Mitigations
| Failure | Impact | Mitigation | Future Enhancement |
|---------|--------|------------|--------------------|
| Adapter exception | Missing data classification | Retry scheduling | Adapter-specific error codes |
| Platform outage (breaker open) | All fetches short-circuit to missing | Circuit breaker state reduces load | Differentiate breaker vs genuine missing in status/fields |
| Duplicate job enqueue | Double trust delta risk | (Current) none explicit | Idempotency token / trust event guard |
| Retry stampede | Load spikes on recovery | Linear backoff (MVP) | Exponential backoff w/ jitter |
| Alert storm | Ops noise | None yet | Rate limiting / aggregation |

## 9. Configuration Surfaces
- `RECONCILIATION_SETTINGS`: tolerances, growth allowance, discrepancy tiers.
- `RETRY_POLICY`: attempt caps & delay for missing/incomplete states.
- `TRUST_SCORING`: event deltas & thresholds for bucketting.
- `ALERTING_SETTINGS`: repeat window for escalation.
- `QUEUE_SETTINGS`: priority weights, capacity warnings.
- `CIRCUIT_BREAKER`: failure threshold, cooldown, probe count.
- `BACKOFF_POLICY`: exponential backoff parameters for failed operations.

**Configuration Override**: All settings can be overridden via environment variables (e.g., `MOCK_FAILURE_RATE`, `REDDIT_LINK_RESOLVE_TIMEOUT`). In production deployments, these would typically be managed through a configuration service or environment-specific config files.

## 10. Extensibility Points
| Area | Hook | Extension Path |
|------|------|----------------|
| New platform | Add adapter in `app.integrations.<name>` with `fetch_post_metrics` | No engine change required |
| Alternate trust policy | Modify `TRUST_SCORING` or replace function | Keep interface `apply_trust_event` |
| Alert rule expansion | Add branch in `maybe_create_alert` | Keep log atomic commit |
| Queue backend swap | Implement interface-compatible enqueue/dequeue | Worker unchanged |
| Persistence store change | Replace engine in `database.py` | Models preserved |

## 10.1 Recent Architecture Additions
| Component | Purpose | Integration Point |
|-----------|---------|-------------------|
| Discord Bot Service | Automated moderation notifications | `app/services/discord_bot.py` |
| Data Quality Validators | Input validation & data integrity checks | `app/services/data_quality_validators.py` |
| Observability Framework | Metrics collection & monitoring | `app/utils/observability.py` |
| Circuit Breaker (In-Memory) | Platform integration resilience | `app/utils/circuit_breaker.py` |
| Backoff & Retry Logic | Exponential backoff for failed operations | `app/utils/backoff.py` |

## 11. Non-Goals (Explicit) 
- Distributed queue (single-process MVP only).
- Cross-process circuit breaker synchronization.
- Real-time streaming reconciliation (batch & async only now).
- Auto re-enqueue of scheduled retries (external scheduler TBD).

## 12. Open Questions / Future Decisions
- Should circuit-open classify as distinct status for richer analytics? (Planned.)
- How to ensure at-most-once trust application on replays? (Introduce reconciliation attempt entity or idempotency key.)
- Introduce partial severity tiers? (Requires weighing confidence_ratio.)

## 13. Quick Glossary
| Term | Definition |
|------|------------|
| Affiliate Report | Affiliate's claimed metrics for a post submission. |
| Reconciliation Attempt | A single execution of `run_reconciliation` (tracked via attempt_count). |
| Platform Report | Snapshot of fetched metrics for an attempt. |
| Discrepancy Level | Qualitative bucket LOW/MEDIUM/HIGH/CRITICAL for classification & alerting. |
| Trust Event | Named event that updates affiliate trust score per config. |
| Confidence Ratio | Fraction of expected metrics present (0–1) for partial data. |

## 14. Onboarding Checklist (Engineer)
1. Read this overview.
2. Skim `RECONCILIATION_ENGINE.md` for algorithm specifics.
3. Run tests (`pytest`) to see green baseline.
4. Add a dummy adapter & test submission to understand flow.
5. Inspect logs for reconciliation job lifecycle.

---
