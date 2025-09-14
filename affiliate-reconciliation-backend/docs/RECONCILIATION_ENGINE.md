# Reconciliation Engine

Technical specification of the `run_reconciliation` function and its collaborating services. This engine orchestrates the complete reconciliation workflow: loading affiliate reports, fetching platform metrics, classifying discrepancies, applying trust scoring, scheduling retries, and triggering alerts.

## 1. Objectives
| Objective | Implementation Strategy |
|-----------|-------------------------|
| Convert claimed vs platform metrics into authoritative status | Deterministic classification function (`classify`) |
| Minimize API latency | Asynchronous queue + background worker |
| Preserve audit trail | Single log + per-attempt platform snapshots |
| Govern trust evolution | Configurable trust event deltas |
| Surface actionable anomalies | Alert rules integrated pre-commit |
| Provide retry for transient gaps | Scheduled retry timestamps for missing / incomplete data |

## 2. Lifecycle (Expanded Step Trace)
1. Load `AffiliateReport` (with Post ↔ Affiliate ↔ Platform relationships).
2. Ensure a `ReconciliationLog` row exists (create placeholder if first attempt).
3. Determine elapsed hours since report submission (growth allowance input).
4. Call `PlatformFetcher.fetch(platform_name, post.url)`.
5. Extract platform metrics (views/clicks/conversions) or classify failure.
6. Invoke `classify(...)` with claimed, platform, elapsed, partial_missing list.
7. Apply trust scoring if classification includes a trust event.
8. Persist `PlatformReport` if any metric observed (non-None).
9. Update `ReconciliationLog` fields (diffs, pct diffs, attempt_count, status, discrepancy level, confidence ratio, missing fields, error codes, trust delta).
10. Compute next retry via `_schedule_retry(status, attempt_count, submitted_at, now)`.
11. Set `post.is_reconciled = True` if terminal and no retry.
12. Invoke `maybe_create_alert` with retry_scheduled flag.
13. Commit transaction.
14. Return structured summary dict (API-friendly, currently used for internal worker tests).

### Return Value Structure
```python
{
    "affiliate_report_id": int,
    "status": str,  # ReconciliationStatus enum value
    "attempt_count": int,
    "scheduled_retry_at": str | None,  # ISO format datetime
    "trust_delta": float,  # 0.0 if no change
    "new_trust_score": float,
    "discrepancy_level": str | None,
    "max_discrepancy_pct": float | None,
    "rate_limited": bool,
    "error_code": str | None,
    "missing_fields": list[str],
}
```

## 3. Classification Algorithm Details
Core logic lives in `discrepancy_classifier.classify`:

| Phase | Logic |
|-------|-------|
| Missing detection | If all platform metrics None → MISSING_PLATFORM_DATA (confidence_ratio=0) |
| Partial detection | Count provided metrics; if 1-2 present → INCOMPLETE_PLATFORM_DATA |
| Growth allowance | Adjust platform metrics upward by growth_per_hour * min(elapsed_hours, cap_hours) |
| Discrepancy calc | discrepancy = claimed - adjusted_platform; pct diff uses ((claimed - adjusted)/adjusted) |
| Overclaim | If any metric diff ≥ overclaim_threshold and positive → AFFILIATE_OVERCLAIMED (CRITICAL if ≥ critical threshold) |
| Base tolerance | If max_diff ≤ base_tolerance → MATCHED |
| Tiers | Else assign LOW/MEDIUM/HIGH based on configured cutoffs |
| Trust events | Mapped: PERFECT_MATCH, MINOR_DISCREPANCY, MEDIUM_DISCREPANCY, HIGH_DISCREPANCY, OVERCLAIM |

### Growth Allowance Rationale
Affiliates may submit slightly ahead of the platform’s ingestion/aggregation; we allow limited growth (bounded by `growth_cap_hours`) to reduce false positives.

## 4. Retry Scheduling Policy
| Status | Policy |
|--------|--------|
| MISSING_PLATFORM_DATA | Linear backoff: initial_delay_minutes * attempt_count (bounded by max_attempts & window_hours) |
| INCOMPLETE_PLATFORM_DATA | Allow one additional follow-up attempt with fixed 15 min delay |
| Others | No retry scheduled |

### Implementation Details
- **Linear Backoff**: `delay_minutes = initial_delay_minutes * max(1, attempt_count)`
- **Missing Data**: Max 5 attempts within 24-hour window, starting with 30-minute delay
- **Incomplete Data**: Single additional attempt allowed if `attempt_count <= 1 + max_additional_attempts`
- **Window Check**: No retry if `(now - submitted_at).total_seconds() / 3600.0 > window_hours`

## 5. Trust Scoring Integration
| Event | Typical Scenario | Delta (config) | Side Effects |
|-------|------------------|----------------|--------------|
| PERFECT_MATCH | All metrics within tolerance | +0.01 (example) | Increment `accurate_submissions` |
| MINOR_DISCREPANCY | Slight under/over within low tier | small negative | None |
| MEDIUM_DISCREPANCY | Moderate variance | moderate negative | None |
| HIGH_DISCREPANCY | Large variance not overclaim | larger negative | None |
| OVERCLAIM | Significant affiliate inflation | largest negative | Fraud-focused alert possible |

Deltas clamp trust within [min_score, max_score]. Trust change recorded as `trust_delta` on log (nullable if zero).

## 6. Alerting Hooks
`maybe_create_alert` invoked before commit so alert is atomic with reconciliation outcome.
- **Overclaim**: `HIGH_DISCREPANCY`, category=`FRAUD`, severity `HIGH` or `CRITICAL` if `discrepancy_level == CRITICAL`
- **High Discrepancy**: `HIGH_DISCREPANCY`, category=`DATA_QUALITY`, severity `HIGH`; escalates to `CRITICAL` if repeat within window
- **Missing Terminal**: `MISSING_DATA`, category=`SYSTEM_HEALTH`, severity `MEDIUM` (only when no retry scheduled)

Idempotency: One alert per reconciliation log. Repeat detection checks for similar alerts within `repeat_overclaim_window_hours`.

## 7. Error & Failure Classification
PlatformFetcher returns `FetchOutcome`:
| Field | Meaning |
|-------|---------|
| success | True if adapter provided data |
| platform_metrics | Dict metrics or None |
| partial_missing | Missing metric names (subset) |
| attempts | Number of in-attempt retries tried |
| error_code | fetch_error / rate_limited / auth_error / circuit_open (indirect) |
| rate_limited | Whether at least one attempt hit rate limit |

Current limitation: circuit breaker denial sets `error_code=reason` but classification path only sees absence of metrics (mapped to missing). Planned: dedicated missing_reason.

## 8. Idempotency & Concurrency Concerns
| Scenario | Current Behavior | Risk |
|----------|------------------|------|
| Duplicate job consumed twice quickly | Each run increments attempt_count; trust event re-applied | Double trust delta |
| Retry after terminal status (no guard) | Status may still reclassify same outcome | Minor reprocessing cost |
| Concurrent trust updates on same affiliate | Serial in single-process MVP | Scale risk if multi-worker introduced |

Mitigations (Backlog):
- Add `last_trust_event_applied` to log; skip if unchanged.
- Introduce Attempt entity keyed by (affiliate_report_id, attempt_index) to enforce uniqueness.

## 9. Terminal vs Non-Terminal Determination
Terminal statuses short-circuit further automatic reconciliation only when no `scheduled_retry_at` is set. `Post.is_reconciled` flips true to avoid repeated queueing. Partial & missing keep `is_reconciled` False.

Terminal statuses include:
- `MATCHED`
- `AFFILIATE_OVERCLAIMED`
- `DISCREPANCY_HIGH`

## 10. Error Handling & Session Management
| Scenario | Handling |
|----------|----------|
| StaleDataError on commit | Retry once with session.merge(), log on second failure |
| Missing AffiliateReport | Raise ValueError with report ID |
| Platform fetch failures | Captured in FetchOutcome, logged in reconciliation log |
| Trust scoring errors | Defensive handling with default trust score (0.5) |

Session lifecycle:
- Fresh SQLAlchemy session per reconciliation job
- Proper cleanup in finally block (worker responsibility)
- Atomic alert creation before commit

## 11. Partial Data Semantics
- `confidence_ratio = observed_metric_count / 3`.
- Discrepancy percentages only computed for present metrics; others excluded from max_diff.
- Trust neutrality: no trust event triggered on partial to avoid penalizing platform unavailability.

## 12. Circuit Breaker Interaction
- On breaker OPEN, call is denied early → classification path → missing.
- Failures (including rate-limited) count toward breaker threshold (future refinement: treat rate limit separately).

## 13. Logging & Observability Points
| Log Location | Purpose |
|--------------|---------|
| Worker start/finish | Operational heartbeat |
| Platform fetch retries | Performance tuning & adapter stability |
| Alert creation | Security / fraud monitoring feed |
| Performance timers (submit_new_post) | Latency budgets |

Future: metric counters for attempt latency, status distribution, trust event frequency.

## 14. Configuration Cheat Sheet
| Setting Namespace | Key Examples |
|-------------------|--------------|
| RECONCILIATION_SETTINGS | base_tolerance_pct, discrepancy_tiers, overclaim thresholds |
| RETRY_POLICY | missing_platform_data.{initial_delay_minutes=30, max_attempts=5, window_hours=24}, incomplete_platform_data.{max_additional_attempts=1} |
| TRUST_SCORING | events.{PERFECT_MATCH, MINOR_DISCREPANCY, ...}, min_score, max_score |
| ALERTING_SETTINGS | repeat_overclaim_window_hours=6 |
| CIRCUIT_BREAKER | failure_threshold, open_cooldown_seconds, half_open_probe_count |

## 15. Edge Case Handling
| Edge Case | Behavior |
|-----------|----------|
| All claimed metrics zero, platform None | Missing classification, schedule retry |
| Negative or absurd claimed metrics | (Assumed validated earlier) – classification still runs; future: input sanitizer |
| Rate limit mid-attempt | Treated as failure; attempts continue until max_attempts |
| Auth error | Terminal inside fetch loop (no further in-attempt retries) |

## 16. Example Reconciliation Trace (Annotated)
```
Attempt 1:
  FetchOutcome: success=True metrics={views:100, clicks:10, conversions:1}
  Claimed: (100,10,1) → diffs 0 → MATCHED → trust +0.01
  Retry: none (terminal) → is_reconciled=True
  Alert: none
  Commit
```

```
Attempt 1 (Missing):
  FetchOutcome: success=False metrics=None error_code=fetch_error
  Classification: MISSING_PLATFORM_DATA
  Retry scheduled in 30m (attempt_count=1)
  Trust: none
  Alert: none (not terminal yet)
  Commit
```

## 17. Future Enhancements Backlog (Engine Scope)
| Feature | Benefit |
|---------|---------|
| Attempt entity & idempotency token | Hard guards against double trust deltas |
| Exponential + jitter backoff | Smoother load, avoids synchronized retries |
| Missing reason granularity | Analytics & faster root cause triage |
| Partial severity weighting | More nuance for partial + extreme diff scenario |
| Config schema validation | Prevent misconfig deployment accidents |

---
