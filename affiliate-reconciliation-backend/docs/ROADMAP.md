# Product & Technical Roadmap

Priority-ordered backlog aligned with risk reduction, correctness, and scale readiness.

Legend: (P1 = Immediate / high impact, P2 = Near-term, P3 = Opportunistic)

## 1. Core Correctness & Resilience
| Item | Priority | Rationale | Notes |
|------|----------|-----------|-------|
| Reconciliation idempotency key | P1 | Prevent duplicate trust deltas & alerts on retries | Hash of (affiliate_id, post_id, platform_report_id, classification_epoch) |
| Missing vs Partial classification refinement | P1 | Reduce false MISSING due to transient platform gaps | Add `missing_reason` enum (BREAKER_OPEN, RATE_LIMIT, UNPARSABLE, TRUE_ABSENCE) |
| Structured discrepancy diagnostics | P1 | Debugging & analytics | Persist raw vs adjusted platform metrics deltas JSON |
| Retry backoff strategy improvement | P1 | Avoid thundering herd & wasted attempts | Exponential w/ jitter; cap & dead-letter after N |
| Dead-letter queue (DLQ) | P1 | Visibility into permanently unresolvable cases | Store final error cause & last classification |

## 2. Observability & Ops
| Item | Priority | Rationale | Notes |
|------|----------|-----------|-------|
| Prometheus metrics exporter | P1 | Establish SLO monitoring | FastAPI middleware + worker gauges |
| Structured JSON logging | P1 | Indexability & correlation | Switch logger formatter; add request / job id |
| Trace correlation IDs | P2 | Multi-hop debugging | Generate per submission; propagate through worker |
| Slack / Webhook alert sink | P2 | Faster operational awareness | Map alert severity to channels |
| Platform fetch latency percentile metrics | P2 | Capacity planning | Tag by platform |

## 3. Risk & Scoring Evolution
| Item | Priority | Rationale | Notes |
|------|----------|-----------|-------|
| Trust decay model (time-weighted) | P2 | Reflect stale inactivity risk reduction | Periodic batch job to drift toward neutral |
| Alert suppression / dedupe window | P2 | Lower alert fatigue | Cache (affiliate, type) w/ TTL |
| Composite fraud score (trust + discrepancy velocity) | P3 | Advanced prioritization | Weighted model, feed into review queue |
| Affiliate segmentation tiers | P3 | Differential thresholds for top performers | Configurable per segment |

## 4. Scalability & Architecture
| Item | Priority | Rationale | Notes |
|------|----------|-----------|-------|
| External durable queue (Redis / SQS) | P1 | Survive restarts & scale workers | Must complete idempotency first |
| Horizontal worker pool | P2 | Throughput increase | Shared rate limiting & breaker state needed |
| Sharded circuit breaker state | P2 | Consistent platform protection in cluster | Move to central store (Redis hash) |
| Postgres migration | P2 | Concurrency, indexing, analytics | Add migrations layer (Alembic) |
| Bulk reconciliation replay tool | P3 | Backfill after logic change | Diff safety guardrails |

## 5. Data Quality & Integrity
| Item | Priority | Rationale | Notes |
|------|----------|-----------|-------|
| Platform adapter contract tests | P1 | Prevent silent field drift | JSON schema + golden fixtures |
| Ingest validation layer | P1 | Early rejection of malformed submissions | Pydantic strict models + normalization summary |
| Metrics normalization service | P2 | Handle platform mismatches centrally | Canonical counters registry |
| Historical trend store | P2 | Anomaly detection input | Separate table or TS DB |

## 6. Developer Experience
| Item | Priority | Rationale | Notes |
|------|----------|-----------|-------|
| Local dev compose (app + metrics + db) | P1 | Faster onboarding | docker-compose w/ seed script |
| Makefile / task runner | P1 | Standardized commands | test, lint, run, lint-fix |
| Type coverage enforcement | P2 | Prevent regressions | mypy strict in CI |
| Scenario factory helpers for tests | P2 | Reduce duplication | Domain-specific builders |

## 7. Security & Compliance
| Item | Priority | Rationale | Notes |
|------|----------|-----------|-------|
| API key rotation workflow | P1 | Key hygiene | Versioned keys w/ overlap period |
| Audit log for trust & alerts changes | P2 | Forensic capability | Append-only table |
| Role-based permission model | P2 | Scoped access | Admin vs analyst actions |
| PII minimization review | P3 | Compliance posture | Data inventory audit |

## 8. Product Expansion
| Item | Priority | Rationale | Notes |
|------|----------|-----------|-------|
| New platform adapters (e.g., LinkedIn) | P2 | Market coverage | Contract-first approach |
| Aggregated affiliate performance dashboard | P2 | Customer value | Derive from existing logs |
| Manual reconciliation override UI | P3 | Human-in-the-loop corrections | Writes audit entries |
| Automated clawback recommendation engine | P3 | Actionable fraud resolution | Uses composite fraud score |

## 9. Dependency & Release Management
| Item | Priority | Rationale | Notes |
|------|----------|-----------|-------|
| Versioned config bundle | P1 | Safe rollbacks | Tag + checksum validation |
| Semantic versioning + CHANGELOG | P2 | Transparency | Automate via commit parsing |
| Pre-release staging environment | P2 | Confidence before prod | Replay anonymized prod-like data |

## 10. Acceptance Gates for Promotion to Production
| Gate | Criteria |
|------|----------|
| Correctness | Idempotent reconciliation; zero duplicate trust deltas in soak test |
| Observability | Metrics + structured logs + basic dashboard |
| Reliability | Graceful handling of adapter outage (circuit verified) |
| Scale | Sustained workload test meeting latency SLO |
| Security | API key rotation + secrets externalized |
| Ops Runbook | Updated with real metrics & thresholds |

## 11. Dependency Ordering Highlights
1. Implement idempotency key BEFORE horizontal scaling or external queue.
2. Structured logging BEFORE advanced analytics/alert routing.
3. Retry strategy + DLQ BEFORE alert suppression (reduces false noise baseline).
4. Adapter contract tests BEFORE rapid platform expansion.

## 12. Risks & Mitigations Matrix
| Risk | Impact | Mitigation |
|------|--------|-----------|
| Duplicate processing without idempotency | Trust inflation, noisy alerts | Idempotency key + unique DB constraint |
| Platform metric schema drift | Silent misclassification | Contract tests + adapter schema versioning |
| Alert fatigue | Ignored real fraud | Suppression + severity tuning |
| Scaling w/o durable queue | Data loss on crash | Move to Redis/SQS early |

## 13. Tracking & Governance
Each roadmap item should carry:
- Owner
- Target milestone (quarter)
- Status (planned / in-progress / blocked / complete)
- Measurable success metric

---
This roadmap should be revisited quarterly and after any major incident retro.
