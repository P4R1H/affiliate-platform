# Data Model & Schema Deep Dive

This document describes the persistent domain model, rationale for each entity, and how fields map to business semantics. Where relevant, we call out trade‑offs and future improvements.

## 1. Entity Overview
| Entity | Purpose | Cardinality Highlights |
|--------|---------|-----------------------|
| User (Affiliate) | Participant submitting performance claims | 1↔N AffiliateReports, 1↔N Alerts, 1↔N Campaigns (created) |
| Client | Client organization | 1↔N Users, 1↔N Campaigns |
| Campaign | Marketing initiative grouping posts | N↔M Platforms, 1↔N Posts |
| Platform | Social / traffic source (reddit, instagram, etc.) | N↔M Campaigns, 1↔N Posts |
| Post | A concrete submitted creative / link instance | 1↔1 AffiliateReport (current MVP), 1↔N PlatformReports |
| AffiliateReport | Claimed metrics at submission time | 1↔1 ReconciliationLog |
| ReconciliationLog | Canonical status + diffs across attempts | 1↔N PlatformReports (indirect via Post), 1↔1 Alert (optional) |
| PlatformReport | Snapshot of fetched platform metrics per attempt | Many per Post (attempt-based) |
| Alert | Operational or risk signal tied to a reconciliation outcome | 1↔1 ReconciliationLog |

## 2. Relationship Diagram (Text)
```
Client --< User >-- Campaign (created_by)
    |            
    |            >-- Platform (through CampaignPlatforms association)
    |
    >-- Campaign --< Post >-- AffiliateReport --(1:1)--> ReconciliationLog --(0/1:1)--> Alert
                      \
                       \-- Post (FK)
Post --< PlatformReport (one per successful attempt with any data)
```

## 3. Key Tables & Fields
### User (Affiliate)
| Field | Type | Notes |
|-------|------|-------|
| id | int | PK |
| name | str | Unique constraint |
| email | str | Unique |
| discord_user_id | str | Unique (nullable) |
| api_key | str | Bearer credential for submission endpoints (nullable) |
| is_active | bool | Default: true |
| role | enum | UserRole (AFFILIATE, CLIENT, ADMIN) |
| client_id | int | FK to Client (nullable, required for CLIENT role) |
| trust_score | numeric(3,2) | 0–1 bounded float (config clamps, nullable for CLIENT) |
| last_trust_update | datetime | UTC timestamp (nullable) |
| total_submissions | int | Total number of submissions made (default: 0) |
| accurate_submissions | int | Number of accurate submissions (default: 0) |
| created_at | datetime | UTC timestamp |

### Campaign
| Field | Type | Notes |
|-------|------|-------|
| id | int | PK |
| name | str | Campaign name |
| client_id | int | FK to Client |
| created_by | int | FK to User (creator) |
| start_date | date | Campaign start date |
| end_date | date | Campaign end date (nullable) |
| impression_cap | int | Maximum impressions allowed (nullable) |
| cpm | numeric(10,2) | Cost per thousand impressions (nullable) |
| status | enum | CampaignStatus (ACTIVE, PAUSED, ENDED) |
| created_at | datetime | UTC timestamp |

### Platform
| Field | Type | Notes |
|-------|------|-------|
| id | int | PK |
| name | str | Platform name (unique, indexed) |
| api_base_url | str | Base URL for platform API (nullable) |
| is_active | bool | Whether platform is active (default: true) |
| api_config | json | API configuration settings (nullable) |
| created_at | datetime | UTC timestamp |

### Client
| Field | Type | Notes |
|-------|------|-------|
| id | int | PK |
| name | str | Client organization name (unique, indexed) |
| created_at | datetime | UTC timestamp |
| updated_at | datetime | UTC timestamp (auto-updated) |

### Association Tables
#### campaign_platform_association
Many-to-many relationship between Campaigns and Platforms.
| Field | Type | Notes |
|-------|------|-------|
| campaign_id | int | FK to Campaign (composite PK) |
| platform_id | int | FK to Platform (composite PK) |

### Post
| Field | Type | Notes |
|-------|------|-------|
| id | int | PK |
| campaign_id | int | FK to Campaign |
| user_id | int | FK to User (affiliate) |
| platform_id | int | FK to Platform |
| url | str | Normalized/original URL submitted |
| title | str | Optional title of the post |
| description | str | Optional description of the post |
| is_reconciled | bool | Boolean flag set when terminal reconciliation reached |
| created_at | datetime | UTC timestamp |
| __table_args__ | Unique constraint on `campaign_id`, `platform_id`, `url`, `user_id` |

### AffiliateReport
Represents immutable claimed metrics at submission.
| Field | Type | Notes |
|-------|------|-------|
| id | int | PK |
| post_id | int | FK to Post (1:1 in current design) |
| claimed_views | int | Views claimed by affiliate (default: 0) |
| claimed_clicks | int | Clicks claimed by affiliate (default: 0) |
| claimed_conversions | int | Conversions claimed by affiliate (default: 0) |
| evidence_data | json | JSON blob for screenshots, links, etc. (nullable) |
| suspicion_flags | json | JSON blob for flags captured during submission validation (nullable) |
| submission_method | enum | SubmissionMethod (API, DISCORD) |
| status | enum | ReportStatus (PENDING, VERIFIED, REJECTED) |
| submitted_at | datetime | UTC timestamp |

### ReconciliationLog
One row per AffiliateReport capturing the latest classification + attempt metadata.
| Field | Type | Notes |
|-------|------|-------|
| id | int | PK |
| affiliate_report_id | int | Unique FK to AffiliateReport |
| platform_report_id | int | FK to latest PlatformReport (nullable) |
| status | enum | ReconciliationStatus |
| discrepancy_level | enum | DiscrepancyLevel (LOW/MEDIUM/HIGH/CRITICAL, nullable) |
| views_discrepancy | int | Signed difference (claimed - platform_adjusted, default: 0) |
| clicks_discrepancy | int | Signed difference (claimed - platform_adjusted, default: 0) |
| conversions_discrepancy | int | Signed difference (claimed - platform_adjusted, default: 0) |
| views_diff_pct | numeric(5,2) | Percent diff (positive = overclaim, negative = underclaim, nullable) |
| clicks_diff_pct | numeric(5,2) | Percent diff (positive = overclaim, negative = underclaim, nullable) |
| conversions_diff_pct | numeric(5,2) | Percent diff (positive = overclaim, negative = underclaim, nullable) |
| notes | str | Optional notes (nullable) |
| processed_at | datetime | Timestamp when reconciliation was processed |
| attempt_count | int | Incremented each run (default: 0) |
| last_attempt_at | datetime | Timestamp of last attempt (nullable) |
| scheduled_retry_at | datetime | Next attempt time (nullable) |
| max_discrepancy_pct | numeric(6,2) | Largest non-null diff for severity bucketing (nullable) |
| confidence_ratio | numeric(4,3) | 0–1 fraction of metrics observed (partial data, nullable) |
| missing_fields | json | JSON: {"fields": [..]} when partial/missing (nullable) |
| rate_limited | bool | Boolean toggle for fetch result (default: false) |
| elapsed_hours | numeric(6,2) | Derived (now - submitted_at, nullable) |
| trust_delta | numeric(5,2) | Float delta applied this attempt (nullable) |
| error_code | str | Adapter/circuit classification (fetch_error, rate_limited, etc., nullable) |
| error_message | str | Free-form diagnostic (nullable) |

### PlatformReport
Historical snapshot of platform metrics returned on a reconciliation attempt when at least one metric is present.
| Field | Type | Notes |
|-------|------|-------|
| id | int | PK |
| post_id | int | FK to Post |
| platform_id | int | FK to Platform |
| views | int | Captured views metric (0 if None) |
| clicks | int | Captured clicks metric (0 if None) |
| conversions | int | Captured conversions metric (0 if None) |
| raw_data | json | JSON dict {views, clicks, conversions} with potential null values |
| fetched_at | datetime | Attempt timestamp |

### Alert
| Field | Type | Notes |
|-------|------|-------|
| id | int | PK |
| reconciliation_log_id | int | FK to ReconciliationLog |
| user_id | int | FK to User (for filtering, nullable) |
| platform_id | int | FK to Platform (for filtering, nullable) |
| alert_type | enum | AlertType (HIGH_DISCREPANCY, MISSING_DATA, SUSPICIOUS_CLAIM, SYSTEM_ERROR) |
| title | str | Human readable title |
| message | str | Human readable message |
| threshold_breached | json | JSON capturing triggering metrics (nullable) |
| category | enum | AlertCategory (DATA_QUALITY, FRAUD, SYSTEM_HEALTH) |
| severity | enum | AlertSeverity (LOW, MEDIUM, HIGH, CRITICAL) |
| status | enum | AlertStatus (OPEN, RESOLVED) |
| resolved_by | str | User who resolved the alert (nullable) |
| resolved_at | datetime | Resolution timestamp (nullable) |
| resolution_notes | str | Resolution notes (nullable) |
| created_at | datetime | UTC timestamp |

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
| Alert recent high discrepancy scans | (user_id, platform_id, created_at DESC) | Supports repeat escalation lookup |
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
WHERE r.discrepancy_level IN ('MEDIUM','HIGH') AND p.user_id = :userId
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

## 13. Analytics (MVP) Derived Metrics
The campaign analytics endpoint (`GET /api/v1/analytics/campaigns/{id}`) returns pre-aggregated, minimal metrics without historical slicing.

| Field | Source Tables | Logic |
|-------|---------------|-------|
| totals.posts | posts | `COUNT(posts.id)` filtered by `campaign_id` |
| totals.views / clicks / conversions | platform_reports JOIN posts | `SUM(platform_reports.metric)` NULL-safe via COALESCE |
| reconciliation.pending_reports | affiliate_reports LEFT JOIN reconciliation_logs | `COUNT(affiliate_reports WHERE reconciliation_logs.id IS NULL)` |
| reconciliation.total_reconciled | affiliate_reports | `total_reports - pending_reports` |
| reconciliation.success_rate | reconciliation_logs | `success_reports / total_reconciled` (success = MATCHED, DISCREPANCY_LOW); NULL if zero reconciled |
| platform_breakdown[] | platform_reports JOIN posts JOIN platforms | Grouped sums per platform (views, clicks, conversions) |
| recent_alerts[] | alerts JOIN reconciliation_logs JOIN affiliate_reports JOIN posts | 5 most recent alerts for campaign |

Design decisions:
1. Success rate excludes medium/high discrepancies & overclaims to present a correctness indicator instead of raw reconciliation completion.
2. NULL success_rate for zero reconciled reports avoids misleading 0.0 implication of failure.
3. No date filtering to keep query simple (future: optional `start_date`, `end_date`, caching layer, materialized view).
4. Platform metrics use platform truth (`platform_reports`) rather than affiliate claims for advertiser‑facing fidelity.

Future enhancements:
* Time-bucketed trend endpoints (daily aggregates) via materialized table.
* Inclusion of discrepancy class distribution histogram.
* Per-platform success_rate breakdown for operational triage.
