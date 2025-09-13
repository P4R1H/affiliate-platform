# Data Model & Schema Deep Dive

This document describes the persistent domain model, rationale for each entity, and how fields map to business semantics. Where relevant, we call out trade‑offs and future improvements.

## 1. Entity Overview
| Entity | Purpose | Cardinality Highlights |
|--------|---------|-----------------------|
| Affiliate | Participant submitting performance claims | 1↔N AffiliateReports, 1↔N Alerts |
| Campaign | Marketing initiative grouping posts | N↔M Platforms, 1↔N Posts |
| Platform | Social / traffic source (reddit, instagram, etc.) | N↔M Campaigns, 1↔N Posts |
| Post | A concrete submitted creative / link instance | 1↔1 AffiliateReport (current MVP), 1↔N PlatformReports |
| AffiliateReport | Claimed metrics at submission time | 1↔1 ReconciliationLog |
| ReconciliationLog | Canonical status + diffs across attempts | 1↔N PlatformReports (indirect via Post), 1↔1 Alert (optional) |
| PlatformReport | Snapshot of fetched platform metrics per attempt | Many per Post (attempt-based) |
| Alert | Operational or risk signal tied to a reconciliation outcome | 1↔1 ReconciliationLog |

## 2. Relationship Diagram (Text)
```
Affiliate --< Post >-- Campaign
    |            
    |            >-- Platform (through CampaignPlatforms association)
    |
    >-- AffiliateReport --(1:1)--> ReconciliationLog --(0/1:1)--> Alert
                      \
                       \-- Post (FK)
Post --< PlatformReport (one per successful attempt with any data)
```

## 3. Key Tables & Fields
### Affiliate
| Field | Type | Notes |
|-------|------|-------|
| id | int | PK |
| name | str | Unique constraint (combined with defensive randomization in tests) |
| email | str | Unique |
| api_key | str | Bearer credential for submission endpoints |
| trust_score | numeric(?,?) | 0–1 bounded float (config clamps) |
| accurate_submissions | int | Incremented on PERFECT_MATCH events |
| last_trust_update | datetime | Auditing trust evolution |

### Campaign
| Field | Notes |
|-------|------|
| id, name, advertiser_name | Basic identity |
| status | Enum (ACTIVE, etc.) |
| start_date | For future growth allowances / SLA windows |
| platforms (relationship) | M:N via association table (not shown here) |

### Platform
| Field | Notes |
|-------|------|
| id, name | Name used for dynamic adapter import |
| api_base_url | Placeholder; useful for future outbound API metadata |

### Post
| Field | Notes |
|-------|------|
| id | PK |
| campaign_id | FK Campaign |
| affiliate_id | FK Affiliate |
| platform_id | FK Platform |
| url | Normalized / original URL submitted |
| title | Optional title of the post |
| description | Optional description of the post |
| is_reconciled | Boolean flag set when terminal reconciliation reached (matched / overclaim / high discrepancy without retry) |
| __table_args__ | Unique constraint on `campaign_id`, `platform_id`, `url`, `affiliate_id` |

### AffiliateReport
Represents immutable claimed metrics at submission.
| Field | Notes |
|-------|------|
| id | PK |
| post_id | FK Post (1:1 in current design) |
| claimed_views / clicks / conversions | Integers as claimed by affiliate |
| evidence_data | JSON blob for screenshots, links, etc. |
| suspicion_flags | JSON blob for flags captured during submission validation |
| submission_method | Enum (API, DISCORD, etc.) |
| status | Enum (PENDING, VERIFIED, REJECTED) |
| submitted_at | Timestamp (UTC) |

### ReconciliationLog
One row per AffiliateReport capturing the latest classification + attempt metadata.
| Field | Notes |
|-------|------|
| id | PK |
| affiliate_report_id | Unique FK -> AffiliateReport |
| status | Enum `ReconciliationStatus` |
| attempt_count | Incremented each run |
| last_attempt_at | Timestamp of last attempt |
| elapsed_hours | Derived (now - submitted_at) |
| views_discrepancy / clicks_discrepancy / conversions_discrepancy | Signed difference (claimed - platform_adjusted) |
| views_diff_pct / clicks_diff_pct / conversions_diff_pct | Percent diff (positive = overclaim, negative = underclaim) |
| max_discrepancy_pct | Largest non-null diff for severity bucketing |
| discrepancy_level | LOW / MEDIUM / HIGH / CRITICAL (None for matched or partial) |
| confidence_ratio | 0–1 fraction of metrics observed (partial data) |
| missing_fields | JSON: {"fields": [..]} when partial/missing |
| trust_delta | Float delta applied this attempt (nullable) |
| platform_report_id | FK to latest PlatformReport (for convenience) |
| scheduled_retry_at | Next attempt time (nullable) |
| error_code | Adapter/circuit classification (fetch_error, rate_limited, etc.) |
| error_message | Free-form diagnostic |
| rate_limited | Boolean toggle for fetch result |

### PlatformReport
Historical snapshot of platform metrics returned on a reconciliation attempt when at least one metric is present.
| Field | Notes |
|-------|------|
| id | PK |
| post_id | FK Post |
| platform_id | FK Platform |
| views / clicks / conversions | Captured metrics (0 substituted if None to keep non-null; raw presence encoded in raw_data) |
| raw_data | JSON dict {views, clicks, conversions} with potential `null` values |
| created_at | Attempt timestamp |

### Alert
| Field | Notes |
|-------|------|
| id | PK |
| reconciliation_log_id | FK ReconciliationLog (unique) |
| affiliate_id / platform_id | For filtering & analytics |
| alert_type | HIGH_DISCREPANCY / MISSING_DATA |
| category | FRAUD / DATA_QUALITY / SYSTEM_HEALTH |
| severity | LOW / MEDIUM / HIGH / CRITICAL |
| title / message | Human readable context |
| threshold_breached | JSON capturing triggering metrics (e.g. max_discrepancy_pct) |
| status | OPEN / RESOLVED (resolution flow future extensibility) |
| created_at / resolved_at | Audit timeline |

## 4. Rationale & Trade-offs
| Choice | Rationale | Alternative Rejected |
|--------|-----------|----------------------|
| Single ReconciliationLog per report | Fast “current status” lookup; simpler trust aggregation | Append-only attempt log table (would require window function queries) |
| Separate PlatformReport snapshots | Audit & historical trending; decouple platform growth | Overwriting last metrics in log (loses history) |
| Store diffs + pct | Avoid recomputation join with claimed metrics; simplifies analytics | Derive on the fly (extra compute / index) |
| JSON for missing_fields / threshold_breached | Flexible, schema-lite MVP | Separate tables (premature normalization) |
| Trust delta stored on log | Transparent provenance of trust shifts | Aggregate only (would obscure per-attempt impact) |

## 5. Invariants & Constraints
1. Exactly one `ReconciliationLog` per `AffiliateReport` (enforced via unique FK).
2. `trust_score` always 0 ≤ score ≤ 1 (clamped by logic, could add DB CHECK later).
3. `attempt_count` monotonically increases; never reset.
4. `PlatformReport` only created when at least one metric is non-null (prevents meaningless empty rows).
5. If `status` ∈ {MATCHED, AFFILIATE_OVERCLAIMED, DISCREPANCY_HIGH} and no scheduled retry, `Post.is_reconciled = True`.

## 6. Indexing & Performance (Future Enhancements)
| Query Use Case | Recommended Index (future) | Notes |
|----------------|----------------------------|-------|
| Fetch logs by status for dashboard | (status, last_attempt_at DESC) | Pagination support |
| Retry scheduler scanning | (scheduled_retry_at WHERE scheduled_retry_at IS NOT NULL) | Narrow index |
| Alert recent high discrepancy scans | (affiliate_id, platform_id, created_at DESC) | Supports repeat escalation lookup |
| Fraud analytics by discrepancy tier | (discrepancy_level, max_discrepancy_pct) | Histogram-friendly |

## 7. Data Quality Considerations
- Partial data: `confidence_ratio` quantifies reliability; downstream analytics should weight metrics accordingly.
- Missing vs Circuit Breaker: Currently indistinguishable in data model; planned addition of explicit `origin` field (e.g., `missing_reason`).
- Rate-limited attempts: flagged via `rate_limited`; not treated differently for failures yet, may require a separate counter to avoid breaker inflation.

## 8. Potential Future Fields
| Field | Entity | Purpose |
|-------|--------|---------|
| attempt_index | PlatformReport | Direct mapping to attempt_count for easier joins |
| missing_reason | ReconciliationLog | Distinguish `fetch_error`, `circuit_open`, `auth_error` |
| trust_version | Affiliate | Allow backwards-compatible scoring changes |
| alert_escalated_from_id | Alert | Reference prior alert when escalating severity |

## 9. Data Lifecycle & Retention
- ReconciliationLog + PlatformReports grow over time; retention strategy could archive stale PlatformReports after N days while retaining aggregated metrics.
- Alerts retained indefinitely for compliance / audit until archiving policy defined.
- Trust score derived from cumulative events; if history is pruned, consider snapshotting cumulative trust provenance.

## 10. Common Query Patterns (Examples)
```sql
-- Count unresolved overclaim alerts
SELECT COUNT(*) FROM alerts WHERE alert_type='HIGH_DISCREPANCY' AND category='FRAUD' AND status='OPEN';

-- Recent medium/high discrepancies by affiliate
SELECT r.* FROM reconciliation_logs r
JOIN affiliate_reports ar ON r.affiliate_report_id = ar.id
JOIN posts p ON ar.post_id = p.id
WHERE r.discrepancy_level IN ('MEDIUM','HIGH') AND p.affiliate_id = :affId
ORDER BY r.last_attempt_at DESC LIMIT 50;

-- Average confidence ratio for partial data last 24h
SELECT AVG(confidence_ratio) FROM reconciliation_logs
WHERE status='INCOMPLETE_PLATFORM_DATA' AND last_attempt_at >= CURRENT_TIMESTAMP - INTERVAL 1 DAY;
```

## 11. Data Integrity Risks & Mitigations
| Risk | Impact | Mitigation | Future |
|------|--------|------------|--------|
| Double trust application on duplicate reconciliation | Inflated trust or penalties | Current test isolation; low concurrency assumption | Add idempotent attempt hashing |
| Missing classification due to growth allowance misconfig | False overclaims | Config validation (TODO) | Dynamic config health checks |
| Alert flood on large batch overclaims | Ops fatigue | None | Introduce rate limit / aggregation |

## 12. Migration Considerations
- Adding attempt_index to PlatformReport: backfill by matching creation order per post + log.attempt_count mapping.
- Splitting missing_reason: retroactive classification could inspect error_message substrings (best effort).
- Introducing multi-log attempt entity: would copy existing log into initial attempt record, keep ReconciliationLog as a view of latest.

---
**Next:** `RECONCILIATION_ENGINE.md` for algorithm internals.
