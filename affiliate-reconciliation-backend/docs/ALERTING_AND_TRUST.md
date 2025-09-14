# Alerting & Trust Scoring

This document explains how we convert reconciliation outcomes into operational / fraud alerts and continuous trust score evolution.

## 1. Design Principles
| Principle | Explanation |
|-----------|-------------|
| Signal over noise | Only high-severity or actionable anomalies raise alerts now |
| Deterministic first | Rule-based system before ML anomaly detection |
| Transparent trust math | Each shift traceable to a single event delta |
| Separation of domains | Alerting logic independent from trust scoring so policies evolve independently |

## 2. Alert Taxonomy
| Alert Type | Category | Typical Trigger | Severity Basis |
|------------|----------|-----------------|---------------|
| HIGH_DISCREPANCY (Overclaim) | FRAUD | Affiliate exceeds platform metric tolerance threshold | Discrepancy level (HIGH/CRITICAL) |
| HIGH_DISCREPANCY (Platform Higher) | DATA_QUALITY | Large variance where affiliate under-reports | Always HIGH; escalate to CRITICAL on repeat |
| MISSING_DATA | SYSTEM_HEALTH | Missing platform metrics after retry exhaustion | Fixed MEDIUM |

## 3. Alert Creation Rules
| Rule | Conditional | Action |
|------|------------|--------|
| R1 | status == AFFILIATE_OVERCLAIMED | Create HIGH_DISCREPANCY alert (FRAUD) severity HIGH/CRITICAL |
| R2 | status == DISCREPANCY_HIGH (non-overclaim) | Create HIGH_DISCREPANCY alert (DATA_QUALITY); escalate if prior high discrepancy alert within repeat window |
| R3 | status == MISSING_PLATFORM_DATA AND no further retry | Create MISSING_DATA alert (SYSTEM_HEALTH) |

Repeat detection window: `ALERTING_SETTINGS.repeat_overclaim_window_hours` (reused for high discrepancy repeat escalation). Currently any prior HIGH_DISCREPANCY counts (does not filter by severity).

## 4. Alert Entity Semantics
| Field | Meaning |
|-------|---------|
| alert_type | Business classification (HIGH_DISCREPANCY, MISSING_DATA) |
| category | Domain slice (FRAUD, DATA_QUALITY, SYSTEM_HEALTH) for routing |
| severity | Intervention urgency (MEDIUM/HIGH/CRITICAL) |
| threshold_breached | JSON payload capturing level + max_discrepancy_pct or attempts |
| status | OPEN → (RESOLVED) future resolution workflow |

## 5. Idempotency & Escalation
- One alert per `ReconciliationLog` (FK uniqueness) → prevents duplicate alerts for the same attempt.
- Escalation currently realized via creating a *new* alert on the next high discrepancy rather than mutating existing alert (simplifies atomicity). Future: escalate in-place or link alerts via `alert_escalated_from_id`.

## 6. Trust Scoring Overview
### Philosophy
A lightweight confidence metric rewarding accuracy, penalizing discrepancies proportionally. Bounded 0–1 to simplify bucket-driven policy decisions (e.g., queue priority alteration, manual review triggers).

### Event → Delta Mapping (Example Configuration)
| TrustEvent | Description | Typical Delta | Rationale |
|------------|-------------|---------------|-----------|
| PERFECT_MATCH | Within base tolerance | +0.01 | Small reinforcement of good behavior |
| MINOR_DISCREPANCY | Low-tier deviation | -0.01 | Mild penalty, could be noise |
| MEDIUM_DISCREPANCY | Mid-tier deviation | -0.03 | Noticeable variance |
| HIGH_DISCREPANCY | High non-overclaim variance | -0.05 | Elevated risk |
| OVERCLAIM | Significant inflation | -0.10 | Strong deterrence / fraud signal |

Final deltas reflect config values; above illustrates relative scale.

### Computation Details
1. Retrieve delta from `TRUST_SCORING.events[event.value]`.
2. Add to current score.
3. Clamp within `[min_score, max_score]`.
4. Record effective delta (post-clamp) in `ReconciliationLog.trust_delta`.
5. Increment `affiliate.accurate_submissions` only on `PERFECT_MATCH` (foundation for future accuracy ratio metrics).

### Buckets (Qualitative)
| Bucket | Condition | Intended Use |
|--------|----------|--------------|
| high_trust | score ≥ reduced_frequency_threshold | Lower reconciliation frequency (future) |
| normal | default band | Standard processing |
| low_trust | score ≥ manual_review_threshold (below increased_monitoring) | Elevated monitoring |
| critical | score < manual_review_threshold | Manual review / potential suspension |

## 7. Interplay: Alerts vs Trust
| Scenario | Alert? | Trust Event? | Combined Effect |
|----------|--------|--------------|-----------------|
| Overclaim (critical) | Yes (CRITICAL) | OVERCLAIM (-large) | Immediate fraud signal + strong trust drop |
| High discrepancy (non-overclaim) w/ repeat | Yes (CRITICAL) | HIGH_DISCREPANCY (-mid) | Escalated ops action and moderate trust penalty |
| Missing (terminal) | Yes (MEDIUM) | None | Operational follow-up; neutral trust until evidence |
| Partial data | No | None | Wait for fuller data; trust neutral |
| Perfect match | No | PERFECT_MATCH (+small) | Slow confidence accretion |

## 8. Rationale & Trade-offs
| Decision | Reason | Alternative |
|----------|-------|------------|
| Separate trust & alerts | Avoid coupling policy changes | Single composite risk score (opaque) |
| No partial penalties | Data unavailability is not user fault | Penalize partial (would punish platform outages) |
| Larger negative for overclaim than positive for match | Asymmetric deterrence | Symmetric (would inflate trust too fast) |
| Repeat escalation via second alert (new row) | Preserves timeline | Mutate in-place (harder audit) |

## 9. Known Limitations / Backlog
| Limitation | Impact | Planned Improvement |
|-----------|--------|---------------------|
| Double trust delta possible on duplicate job | Over/under penalization | Idempotency guard / attempt entity |
| Repeat high discrepancy check coarse (any prior) | Possible over-escalation | Filter by timeframe + severity + metric similarity |
| No alert suppression / rate limiting | Alert storms possible | Rolling window rate cap |
| Trust has no decay | Persistent legacy penalties | Time-decay or rolling window normalization |
| Missing vs circuit-open indistinct | Poor root cause metrics | missing_reason field |

## 10. Example Alert Payloads
```json
{
  "id": 42,
  "alert_type": "HIGH_DISCREPANCY",
  "category": "FRAUD",
  "severity": "CRITICAL",
  "threshold_breached": {"discrepancy_level": "CRITICAL", "max_discrepancy_pct": 0.62},
  "affiliate_id": 10,
  "platform_id": 3,
  "reconciliation_log_id": 77
}
```
```json
{
  "id": 91,
  "alert_type": "MISSING_DATA",
  "category": "SYSTEM_HEALTH",
  "severity": "MEDIUM",
  "threshold_breached": {"attempts": 5},
  "affiliate_id": 10,
  "platform_id": 3,
  "reconciliation_log_id": 88
}
```

## 11. Operational Guidelines
| Situation | Action |
|-----------|--------|
| Sudden spike in OVERCLAIM alerts | Check adapter correctness & affiliate cohort; possible abuse |
| Elevated MISSING_DATA alerts | Inspect circuit breaker snapshots; verify platform API health |
| Trust scores trending down across board | Revisit tolerance/growth config; potential overly strict classification |
| Single affiliate dropping to critical | Consider throttling submissions / manual audit |

## 12. Metrics Roadmap (Not Yet Implemented)
| Metric | Type | Purpose |
|--------|------|---------|
| reconciliation_status_total{status} | Counter | Volume per status |
| trust_event_total{event} | Counter | Frequency of each trust event |
| alert_created_total{type,severity} | Counter | Alert generation trends |
| trust_score_gauge{affiliate_bucket} | Gauge | Distribution monitoring |
| missing_reason_total{reason} | Counter | Root cause of data gaps |

## 13. Example Trust Evolution Trace
```
Initial: 0.50
Match: +0.01 -> 0.51
Medium discrepancy: -0.03 -> 0.48
Overclaim: -0.10 -> 0.38
(No decay yet)
```

## 14. Quick Reference Tables
### Trust Events to Config Keys
`TRUST_SCORING.events.<EVENT_NAME>` maps directly by `TrustEvent.value`.

### Escalation Window
`ALERTING_SETTINGS.repeat_overclaim_window_hours` used for high discrepancy repeat escalation (name legacy of overclaim focus).

---
