# Operations & Observability Runbook

Guidance for running, monitoring, and troubleshooting the reconciliation platform.

## 1. Operational Objectives
| Objective | Description |
|-----------|-------------|
| Timely anomaly detection | Surface fraud or data issues quickly |
| Minimal MTTR | Provide clear diagnostics to resolve failures fast |
| Predictable performance | Stable ingestion latency & processing throughput |
| Transparent state | Ability to answer "what is the status of X" immediately |

## 2. Runtime Components & Ownership
| Component | Responsibility | Owner |
|-----------|---------------|-------|
| API (FastAPI) | Submission handling, CRUD endpoints | Backend |
| Queue | Buffer & prioritize reconciliation jobs | Backend |
| Worker | Execute reconciliation attempts | Backend |
| Circuit Breaker | Integration protection | Backend |
| Alerting Logic | Emission of risk/ops signals | Risk/Backend |
| DB (SQLite test / future RDBMS) | Persistence | DevOps/DBA |

## 3. Logging Conventions
| Logger Pattern | Example | Purpose |
|----------------|---------|---------|
| `app.app.api.*` | `Request started` | Request lifecycle |
| `app.app.jobs.worker_reconciliation` | `Processing reconciliation job` | Worker heartbeat |
| `app.app.services.platform_fetcher` | `Platform fetch retry scheduled` | Adapter stability |
| `app.app.services.alerting` | `Created overclaim alert` | Risk events |
| `performance` (tag) | `Performance: submit_new_post` | Latency timing |

Fields often included: `platform`, `attempt`, `backoff_seconds`, `error_code`, `severity`, enabling downstream parsing.

## 4. Suggested Metrics (Future Implementation)
| Metric | Type | Rationale |
|--------|------|-----------|
| reconciliation_status_total{status} | Counter | Distribution & anomaly spikes |
| reconciliation_attempt_duration_seconds | Histogram | Performance & SLO tracking |
| queue_depth | Gauge | Backpressure early warning |
| worker_idle_ratio | Gauge | Capacity planning |
| alert_created_total{type,severity} | Counter | Fraud vs system health trend |
| trust_score_bucket_total{bucket} | Counter | Risk posture shift |
| breaker_state_total{platform,state} | Counter/Gauge | Platform stability visibility |

## 5. Health Checks / SLO Concepts
| Signal | Acceptable Target (MVP) |
|--------|-------------------------|
| Median submission latency | < 150ms |
| 95th percentile reconciliation attempt time | < 1s (internal) |
| Time from submission to first reconciliation | < 5s (single worker) |
| Queue depth sustained | < 100 (tunable) |
| Missing terminal ratio (24h) | < 5% of total reconciliations |

## 6. Circuit Breaker Runbook
| Symptom | Action |
|---------|--------|
| Frequent `circuit_open` warnings | Confirm upstream platform API availability; consider raising threshold temporarily |
| Rapid OPEN ↔ HALF_OPEN flapping | Increase `open_cooldown_seconds` or reduce `half_open_probe_count` |
| High missing due to breaker | Add missing_reason instrumentation to differentiate true missing |

Breaker Snapshot (internal debug suggestion): add diagnostic endpoint returning `GLOBAL_CIRCUIT_BREAKER.snapshot()` for ops dashboards.

## 7. Troubleshooting Guide
| Issue | Likely Causes | Steps |
|-------|---------------|-------|
| All reconciliations become MISSING | Platform outage, circuit breaker open, adapter import error | Check logs for `fetch_error` vs `circuit_open`; validate adapter module import |
| Trust scores plummet globally | Misconfigured thresholds / growth allowance | Inspect `RECONCILIATION_SETTINGS`; run classifier unit tests with boundary values |
| Alert flood (overclaim) | Real fraud wave or adapter returning low metrics | Sample PlatformReport vs raw affiliate claims to verify adapter integrity |
| Queue depth climbs | Worker stalled, long fetch times, increase in submissions | Check worker logs; profile platform fetch durations |
| Reconciliation log updates failing | DB schema drift / migrations | Inspect DB migrations (future) and error logs |

## 8. Incident Response Playbook (Abbreviated)
1. Classify incident (Fraud surge / External Platform Outage / Internal Degradation).
2. Snapshot metrics (queue depth, status distribution, breaker states).
3. Contain (e.g., temporarily reduce submission acceptance or disable problematic platform).
4. Correct (adapter fix, config adjustment, dependency rollback).
5. Communicate (status channel + retrospective).

## 9. Configuration Changes - Safe Deployment Tips
| Config | Risk | Safe Practice |
|--------|------|--------------|
| Base tolerance | Over/under flagging | Roll out small increments; monitor discrepancy distribution |
| Overclaim threshold | Fraud detection sensitivity | A/B test on subset (if multi-worker future) |
| Trust deltas | Score inflation / collapse | Simulate on historical sample before apply |
| Circuit breaker threshold | Resilience vs latency | Adjust during off-peak; watch error mix |

## 10. Observability Backlog
| Item | Benefit |
|------|--------|
| Structured JSON logs for all services | Easier ingestion into ELK/Datadog |
| Metrics exporter (Prometheus) | Real-time dashboards |
| Alert to Slack/Webhook integration | Faster incident awareness |
| Tracing (OpenTelemetry) | End-to-end latency insight |
| Derived risk dashboard | Single pane of risk posture |

## 11. Security & Access Considerations
| Aspect | Current | Future |
|--------|---------|--------|
| API Auth | Static affiliate API keys | OAuth or key rotation service |
| Data at Rest | SQLite (tests) | Encrypted RDS/Postgres |
| Least Privilege | Single app role | Separate read-only analytics role |
| Secrets Management | .env | Central secret manager |

## 12. Capacity Planning Notes
| Variable | Impact |
|----------|--------|
| Submissions per second | Queue depth linear growth if > worker throughput |
| Average fetch latency | Directly reduces worker capacity | 
| Retry rate (missing) | Multiplies attempt volume | 
| Overclaim frequency | Increases alert volume and potential manual workload |

Future scaling: horizontal worker pool + distributed queue; ensure idempotent job design first.

## 13. Disaster Recovery (Forward-Looking)
| Scenario | Strategy |
|----------|----------|
| Primary DB loss | Automated backups + restore; replay submission queue if externalized |
| Adapter logic regression | Feature flag / rapid rollback (package versioning) |
| Configuration corruption | Maintain versioned config; validation on load |

## 14. Minimal Local Ops Checklist
1. `pytest` (green tests).
2. Run app locally (uvicorn) & submit sample payload.
3. Confirm reconciliation log & alert (overclaim scenario) created.
4. Review logs for expected worker lifecycle lines.

## 15. Future Runbook Additions
| Planned Section | Trigger |
|-----------------|---------|
| Throttling high-risk affiliates | Queue saturation by low trust bucket |
| Bulk re-reconciliation procedure | Schema change affecting diff calculations |
| Data export for compliance | Audit request |

---
Next: `ROADMAP.md`.
