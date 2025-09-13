# Data Flow Examples

This document provides concrete examples of data flows through the Affiliate Reconciliation Platform, from initial submission to final reconciliation outcomes.

## Overview

The platform processes affiliate submissions through several stages:
1. **Submission** - Affiliate reports metrics via API or Discord
2. **Validation** - System validates data and creates records
3. **Queuing** - Reconciliation job is enqueued with appropriate priority
4. **Fetching** - Platform data is retrieved via integrations
5. **Classification** - Metrics are compared and discrepancies classified
6. **Trust Scoring** - Affiliate trust score is updated based on accuracy
7. **Alerting** - Alerts are generated for significant discrepancies
8. **Response** - Results are made available via API

## Example 1: Perfect Match Scenario

This example shows an affiliate submission that matches platform data exactly.

### Step 1: Affiliate Submission

**Request:**
```http
POST /api/v1/submissions/
Authorization: Bearer aff_john_smith_key
Content-Type: application/json

{
  "campaign_id": 1,
  "platform_id": 1,
  "url": "https://reddit.com/r/technology/posts/abc123",
  "title": "Amazing new AI tool for developers",
  "description": "Review of the latest AI coding assistant",
  "claimed_views": 5000,
  "claimed_clicks": 150,
  "claimed_conversions": 8,
  "evidence_data": {
    "submission_time": "2024-01-15T10:00:00Z",
    "peak_activity_window": "2024-01-15T15:00-17:00",
    "notes": "Posted during optimal engagement hours"
  },
  "submission_method": "API"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Post submitted successfully",
  "data": {
    "post_id": 101,
    "affiliate_report_id": 201,
    "campaign_id": 1,
    "platform_id": 1,
    "url": "https://reddit.com/r/technology/posts/abc123",
    "status": "PENDING",
    "reconciliation_queued": true,
    "priority": "normal",
    "submitted_at": "2024-01-15T10:30:00Z"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Step 2: System Processing

**Database Records Created:**

*posts table:*
```sql
INSERT INTO posts (id, campaign_id, affiliate_id, platform_id, url, title, description, is_reconciled, created_at)
VALUES (101, 1, 5, 1, 'https://reddit.com/r/technology/posts/abc123', 'Amazing new AI tool for developers', 'Review of the latest AI coding assistant', false, '2024-01-15 10:30:00');
```

*affiliate_reports table:*
```sql
INSERT INTO affiliate_reports (id, post_id, claimed_views, claimed_clicks, claimed_conversions, evidence_data, submission_method, status, submitted_at)
VALUES (201, 101, 5000, 150, 8, '{"submission_time": "2024-01-15T10:00:00Z", "peak_activity_window": "2024-01-15T15:00-17:00", "notes": "Posted during optimal engagement hours"}', 'API', 'PENDING', '2024-01-15 10:30:00');
```

### Step 3: Job Queue Processing

**Job Enqueued:**
```json
{
  "job_type": "ReconciliationJob",
  "affiliate_report_id": 201,
  "priority": "normal",
  "enqueued_at": "2024-01-15T10:30:01Z",
  "affiliate_trust_score": 0.78,
  "suspicion_flags": {}
}
```

**Worker Processing Log:**
```
2024-01-15 10:30:02 INFO app.jobs.worker_reconciliation Processing reconciliation job affiliate_report_id=201
2024-01-15 10:30:02 INFO app.services.reconciliation_engine Starting reconciliation for report_id=201
```

### Step 4: Platform Data Fetch

**Reddit Integration Call:**
```json
{
  "post_url": "https://reddit.com/r/technology/posts/abc123",
  "config": {
    "growth_allowance": true,
    "elapsed_hours": 2.5
  }
}
```

**Mock Reddit API Response:**
```json
{
  "ups": 4950,
  "downs": 125,
  "num_comments": 145,
  "total_awards_received": 8,
  "created_utc": 1705314000,
  "subreddit": "technology"
}
```

**Platform Report Created:**
```sql
INSERT INTO platform_reports (id, post_id, platform_id, views, clicks, conversions, raw_data, created_at)
VALUES (301, 101, 1, 4950, 145, 8, '{"ups": 4950, "downs": 125, "num_comments": 145, "total_awards_received": 8, "created_utc": 1705314000, "subreddit": "technology"}', '2024-01-15 10:30:03');
```

### Step 5: Growth Allowance Application

**Growth Calculation:**
- Elapsed time: 2.5 hours since submission
- Growth rate: 10 views/hour (configured)
- Growth allowance: 2.5 * 10 = 25 additional views
- Adjusted platform views: 4950 + 25 = 4975

### Step 6: Discrepancy Classification

**Comparison:**
- Claimed views: 5000
- Adjusted platform views: 4975
- Views difference: 5000 - 4975 = 25 (0.5%)
- Claimed clicks: 150
- Platform clicks: 145
- Clicks difference: 150 - 145 = 5 (3.4%)
- Claimed conversions: 8
- Platform conversions: 8
- Conversions difference: 0 (0%)

**Classification Result:**
- Max discrepancy: 3.4% (within base tolerance of 5%)
- Status: **MATCHED**
- Discrepancy level: None
- Trust event: **PERFECT_MATCH**

### Step 7: Trust Score Update

**Before reconciliation:**
- Affiliate trust score: 0.78
- Accurate submissions: 45
- Total submissions: 58

**Trust scoring calculation:**
- Event: PERFECT_MATCH
- Delta: +0.01 (from configuration)
- New trust score: min(0.78 + 0.01, 1.0) = 0.79

**After reconciliation:**
- Affiliate trust score: 0.79
- Accurate submissions: 46 (+1)
- Total submissions: 58

### Step 8: Reconciliation Log Update

```sql
INSERT INTO reconciliation_logs (id, affiliate_report_id, status, attempt_count, last_attempt_at, elapsed_hours, views_discrepancy, clicks_discrepancy, conversions_discrepancy, views_diff_pct, clicks_diff_pct, conversions_diff_pct, max_discrepancy_pct, discrepancy_level, confidence_ratio, trust_delta, platform_report_id)
VALUES (401, 201, 'MATCHED', 1, '2024-01-15 10:30:03', 2.5, 25, 5, 0, 0.5, 3.4, 0.0, 3.4, NULL, 1.0, 0.01, 301);
```

### Step 9: Final Response

**API Query for Results:**
```http
GET /api/v1/submissions/101/metrics
Authorization: Bearer aff_john_smith_key
```

**Response:**
```json
{
  "success": true,
  "data": {
    "post_id": 101,
    "affiliate_metrics": {
      "claimed_views": 5000,
      "claimed_clicks": 150,
      "claimed_conversions": 8,
      "submission_method": "API",
      "submitted_at": "2024-01-15T10:30:00Z"
    },
    "platform_metrics": {
      "observed_views": 4950,
      "observed_clicks": 145,
      "observed_conversions": 8,
      "growth_adjustment": 25,
      "adjusted_views": 4975,
      "fetched_at": "2024-01-15T10:30:03Z"
    },
    "reconciliation": {
      "status": "MATCHED",
      "discrepancy_level": null,
      "max_discrepancy_pct": 3.4,
      "confidence_ratio": 1.0,
      "attempt_count": 1,
      "last_attempt_at": "2024-01-15T10:30:03Z"
    },
    "trust_impact": {
      "event": "PERFECT_MATCH",
      "previous_score": 0.78,
      "new_score": 0.79,
      "delta": 0.01
    }
  }
}
```

## Example 2: High Discrepancy with Alert

This example shows an affiliate overclaiming metrics, triggering fraud detection.

### Step 1: Suspicious Submission

**Request:**
```http
POST /api/v1/submissions/
Authorization: Bearer aff_suspicious_user_key
Content-Type: application/json

{
  "campaign_id": 1,
  "platform_id": 2,
  "url": "https://instagram.com/p/aBc123DeF/",
  "title": "Viral product showcase",
  "claimed_views": 50000,
  "claimed_clicks": 2500,
  "claimed_conversions": 125,
  "evidence_data": {
    "notes": "Went viral overnight, huge engagement"
  },
  "submission_method": "API"
}
```

### Step 2: Suspicion Flag Detection

During validation, the system detects unusually high conversion rate (2.5%) and flags for priority processing:

**Suspicion flags added:**
```json
{
  "high_conversion_rate": {
    "detected_rate": 2.5,
    "threshold": 1.0,
    "severity": "medium"
  },
  "large_claim": {
    "claimed_views": 50000,
    "threshold": 30000,
    "severity": "low"
  }
}
```

**Priority escalation:**
- Original priority: "normal"
- With suspicion flags: "high"

### Step 3: Platform Data Reveals Discrepancy

**Instagram Integration Response:**
```json
{
  "impressions": 15000,
  "reach": 12000,
  "website_clicks": 180,
  "saves": 45,
  "profile_visits": 120
}
```

**Unified metrics:**
- Platform views: 15000 (impressions)
- Platform clicks: 180 (website_clicks)
- Platform conversions: 165 (saves + profile_visits)

### Step 4: Classification Results

**Discrepancy analysis:**
- Views: 50000 claimed vs 15000 platform = **233% overclaim**
- Clicks: 2500 claimed vs 180 platform = **1289% overclaim**
- Conversions: 125 claimed vs 165 platform = -24% (affiliate underclaimed)

**Classification:**
- Status: **AFFILIATE_OVERCLAIMED**
- Discrepancy level: **CRITICAL**
- Max discrepancy: 1289%
- Trust event: **OVERCLAIM**

### Step 5: Trust Score Impact

**Severe penalty applied:**
- Previous trust score: 0.45
- Overclaim penalty: -0.10
- New trust score: max(0.45 - 0.10, 0.0) = 0.35

### Step 6: Alert Generation

**High discrepancy alert created:**
```sql
INSERT INTO alerts (id, reconciliation_log_id, affiliate_id, platform_id, alert_type, category, severity, title, message, threshold_breached, status, created_at)
VALUES (501, 402, 8, 2, 'HIGH_DISCREPANCY', 'FRAUD', 'CRITICAL', 'Critical overclaim detected', 'Affiliate significantly overclaimed metrics on Instagram post - requires immediate investigation', '{"max_discrepancy_pct": 1289, "overclaim_threshold": 50}', 'OPEN', '2024-01-15 11:15:00');
```

### Step 7: API Response with Alert

**Alert endpoint response:**
```http
GET /api/v1/alerts/
Authorization: Bearer admin_key
```

```json
{
  "success": true,
  "data": [
    {
      "id": 501,
      "alert_type": "HIGH_DISCREPANCY",
      "category": "FRAUD",
      "severity": "CRITICAL",
      "title": "Critical overclaim detected",
      "message": "Affiliate significantly overclaimed metrics on Instagram post - requires immediate investigation",
      "affiliate_name": "Suspicious User",
      "platform_name": "instagram",
      "threshold_breached": {
        "max_discrepancy_pct": 1289,
        "overclaim_threshold": 50
      },
      "status": "OPEN",
      "created_at": "2024-01-15T11:15:00Z",
      "post_url": "https://instagram.com/p/aBc123DeF/"
    }
  ]
}
```

## Example 3: Missing Platform Data with Retry

This example shows how the system handles temporary platform unavailability.

### Step 1: Normal Submission

**Affiliate submits standard post:**
```json
{
  "campaign_id": 2,
  "platform_id": 3,
  "url": "https://tiktok.com/@user/video/1234567890",
  "claimed_views": 25000,
  "claimed_clicks": 300,
  "claimed_conversions": 15
}
```

### Step 2: Platform Integration Failure

**TikTok integration encounters error:**
```
2024-01-15 12:30:05 WARNING app.integrations.tiktok TikTok API timeout post_url=https://tiktok.com/@user/video/1234567890
2024-01-15 12:30:05 INFO app.services.platform_fetcher Fetch failed, scheduling retry attempt=1 backoff_minutes=30
```

### Step 3: Classification as Missing Data

**No platform data available:**
- Status: **MISSING_PLATFORM_DATA**
- Confidence ratio: 0.0
- Trust event: None (neutral)
- Retry scheduled: 30 minutes later

### Step 4: Retry Scheduling

```sql
UPDATE reconciliation_logs 
SET scheduled_retry_at = '2024-01-15 13:00:00', 
    attempt_count = 1, 
    error_code = 'fetch_timeout'
WHERE affiliate_report_id = 203;
```

### Step 5: Successful Retry

**30 minutes later, TikTok API recovers:**
```json
{
  "play_count": 24500,
  "profile_views": 285,
  "share_count": 16,
  "like_count": 1200,
  "comment_count": 45
}
```

**Second attempt succeeds:**
- Status updated: **DISCREPANCY_LOW**
- Views discrepancy: 25000 vs 24500 = 2%
- Trust event: **MINOR_DISCREPANCY**
- No further retries needed

## Example 4: Discord Integration Flow

This example shows how Discord submissions would be processed (when implemented).

### Step 1: Discord Message

**Affiliate posts in Discord channel:**
```
!submit https://youtube.com/watch?v=abc123 
Campaign: Summer Sale 2024
Views: 15000
Clicks: 450  
Conversions: 22
Evidence: https://discord.com/attachments/screenshot.png
```

### Step 2: Discord Bot Processing

**Bot parses message and creates submission:**
```python
# Discord bot extracts data
submission_data = {
    "campaign_id": find_campaign_by_name("Summer Sale 2024"),
    "platform_id": find_platform_by_url("youtube.com"),
    "url": "https://youtube.com/watch?v=abc123",
    "claimed_views": 15000,
    "claimed_clicks": 450,
    "claimed_conversions": 22,
    "evidence_data": {
        "discord_message_id": "1234567890123456789",
        "discord_user_id": "user123456",
        "discord_channel": "#submissions",
        "screenshot_url": "https://discord.com/attachments/screenshot.png",
        "timestamp": "2024-01-15T14:00:00Z"
    },
    "submission_method": "DISCORD"
}
```

### Step 3: API Call from Discord Bot

**Bot makes authenticated API call:**
```http
POST /api/v1/submissions/
Authorization: Bearer aff_discord_user_key
Content-Type: application/json

{...submission_data...}
```

### Step 4: Normal Processing Flow

The submission then follows the standard reconciliation process, with Discord-specific evidence preserved in the `evidence_data` field.

## Example 5: Batch Reconciliation via Manual Trigger

This example shows triggering reconciliation for multiple posts.

### Step 1: Manual Trigger Request

**Admin triggers reconciliation for campaign:**
```http
POST /api/v1/reconciliation/run
Authorization: Bearer admin_key
Content-Type: application/json

{
  "campaign_id": 1,
  "force_reprocess": false,
  "status_filter": ["PENDING", "INCOMPLETE_PLATFORM_DATA"]
}
```

### Step 2: Job Queue Processing

**Multiple jobs enqueued:**
```json
{
  "jobs_enqueued": 15,
  "affiliate_report_ids": [201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215],
  "priority_distribution": {
    "high": 3,
    "normal": 10,
    "low": 2
  },
  "estimated_completion": "2024-01-15T15:30:00Z"
}
```

### Step 3: Bulk Processing Results

**Results summary after completion:**
```http
GET /api/v1/reconciliation/results?campaign_id=1&start_date=2024-01-15T15:00:00Z
```

```json
{
  "success": true,
  "data": {
    "summary": {
      "total_processed": 15,
      "by_status": {
        "MATCHED": 8,
        "DISCREPANCY_LOW": 4,
        "DISCREPANCY_MEDIUM": 2,
        "DISCREPANCY_HIGH": 1,
        "MISSING_PLATFORM_DATA": 0
      },
      "alerts_generated": 1,
      "avg_processing_time_seconds": 2.3,
      "avg_confidence_ratio": 0.97
    },
    "reconciliation_logs": [...]
  }
}
```

## Data Transformation Summary

### Input Data Sources

1. **Affiliate Reports** (API/Discord):
   - Claimed metrics
   - Evidence data
   - Submission metadata

2. **Platform APIs**:
   - Authoritative metrics
   - Engagement data
   - Performance indicators

3. **System Configuration**:
   - Tolerance thresholds
   - Growth allowances
   - Trust scoring rules

### Output Data Products

1. **Reconciliation Results**:
   - Status classifications
   - Discrepancy measurements
   - Confidence assessments

2. **Trust Scores**:
   - Updated affiliate reliability
   - Historical accuracy tracking
   - Behavioral insights

3. **Operational Alerts**:
   - Fraud detection signals
   - Data quality issues
   - System health warnings

4. **Analytics Data**:
   - Performance trends
   - Platform comparisons
   - Campaign effectiveness

## Performance Characteristics

### Processing Times (Typical)

- **Submission validation**: 50-100ms
- **Platform fetch**: 500-2000ms (varies by platform)
- **Classification**: 10-50ms
- **Database updates**: 20-100ms
- **Total end-to-end**: 1-3 seconds

### Throughput Capacity

- **Single worker**: ~100 reconciliations/minute
- **Multi-worker**: Scales linearly with worker count
- **Queue capacity**: 5000+ jobs in memory
- **API throughput**: 1000+ requests/hour per affiliate

### Error Rates

- **Platform fetch failures**: ~5% (simulated)
- **Validation failures**: <1%
- **Retry success rate**: ~90%
- **False positive alerts**: <2%

These examples demonstrate the platform's capability to handle various scenarios while maintaining data integrity, providing transparency, and enabling operational oversight of the affiliate reconciliation process.