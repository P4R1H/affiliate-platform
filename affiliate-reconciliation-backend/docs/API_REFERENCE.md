# API Reference

Complete reference for all REST API endpoints in the Affiliate Reconciliation Platform.

## Base URL
```
http://localhost:8000/api/v1
```

## Authentication
All API endpoints require authentication via Bearer token:
```
Authorization: Bearer {affiliate_api_key}
```

API keys are generated when creating an affiliate account and can be retrieved via the `/affiliates/me` endpoint.

## Response Format
All API responses follow a consistent structure:

```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {
    // Response-specific data here
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

Error responses:
```json
{
  "success": false,
  "message": "Error description",
  "error_code": "VALIDATION_ERROR",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Affiliates

### Create Affiliate
```http
POST /api/v1/affiliates/
```

**Request Body:**
```json
{
  "name": "John Smith",
  "email": "john@example.com",
  "discord_user_id": "user123",
  "role": "AFFILIATE"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Affiliate created successfully",
  "data": {
    "id": 1,
    "name": "John Smith",
    "email": "john@example.com",
    "api_key": "aff_abc123def456",
    "trust_score": 0.50,
    "role": "AFFILIATE",
    "is_active": true,
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

### Get Current Affiliate Profile
```http
GET /api/v1/affiliates/me
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "name": "John Smith",
    "email": "john@example.com",
    "trust_score": 0.85,
    "total_submissions": 42,
    "accurate_submissions": 38,
    "accuracy_rate": 0.90,
    "role": "AFFILIATE",
    "is_active": true,
    "created_at": "2024-01-15T10:30:00Z",
    "last_trust_update": "2024-01-20T15:45:00Z"
  }
}
```

### Update Affiliate Profile
```http
PUT /api/v1/affiliates/me
```

**Request Body:**
```json
{
  "name": "John Smith Jr.",
  "discord_user_id": "newuser456"
}
```

## Campaigns

### Create Campaign (Admin Only)
```http
POST /api/v1/campaigns/
```

**Request Body:**
```json
{
  "name": "Summer Sale 2024",
  "advertiser_name": "TechCorp Inc",
  "status": "ACTIVE",
  "start_date": "2024-06-01",
  "end_date": "2024-08-31",
  "platform_ids": [1, 2, 3]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Campaign created successfully",
  "data": {
    "id": 1,
    "name": "Summer Sale 2024",
    "advertiser_name": "TechCorp Inc",
    "status": "ACTIVE",
    "start_date": "2024-06-01",
    "end_date": "2024-08-31",
    "created_at": "2024-01-15T10:30:00Z",
    "platforms": [
      {"id": 1, "name": "reddit"},
      {"id": 2, "name": "instagram"},
      {"id": 3, "name": "tiktok"}
    ]
  }
}
```

### List Campaigns
```http
GET /api/v1/campaigns/
```

**Query Parameters:**
- `status`: Filter by campaign status (ACTIVE, PAUSED, COMPLETED)
- `limit`: Number of results to return (default: 50)
- `offset`: Pagination offset (default: 0)

**Response:**
```json
{
  "success": true,
  "data": {
    "campaigns": [
      {
        "id": 1,
        "name": "Summer Sale 2024",
        "advertiser_name": "TechCorp Inc",
        "status": "ACTIVE",
        "start_date": "2024-06-01",
        "end_date": "2024-08-31",
        "platform_count": 3
      }
    ],
    "total": 1,
    "limit": 50,
    "offset": 0
  }
}
```

## Submissions

### Submit New Post
```http
POST /api/v1/submissions/
```

**Request Body:**
```json
{
  "campaign_id": 1,
  "platform_id": 1,
  "url": "https://reddit.com/r/technology/posts/abc123",
  "title": "Check out this amazing tech product!",
  "description": "Detailed review of the latest gadget",
  "claimed_views": 15000,
  "claimed_clicks": 450,
  "claimed_conversions": 23,
  "evidence_data": {
    "screenshot_url": "https://example.com/screenshot.png",
    "notes": "Posted during peak hours for maximum visibility"
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
    "post_id": 1,
    "affiliate_report_id": 1,
    "campaign_id": 1,
    "platform_id": 1,
    "url": "https://reddit.com/r/technology/posts/abc123",
    "status": "PENDING",
    "reconciliation_queued": true,
    "priority": "normal",
    "submitted_at": "2024-01-15T10:30:00Z"
  }
}
```

### Update Post Metrics
```http
PUT /api/v1/submissions/{post_id}/metrics
```

**Request Body:**
```json
{
  "claimed_views": 18000,
  "claimed_clicks": 520,
  "claimed_conversions": 28,
  "evidence_data": {
    "updated_screenshot": "https://example.com/updated_screenshot.png",
    "notes": "Updated with latest metrics"
  }
}
```

### Get Submission History
```http
GET /api/v1/submissions/history
```

**Query Parameters:**
- `campaign_id`: Filter by campaign
- `platform_id`: Filter by platform
- `status`: Filter by reconciliation status
- `limit`: Number of results (default: 50)
- `offset`: Pagination offset (default: 0)

**Response:**
```json
{
  "success": true,
  "data": {
    "submissions": [
      {
        "post_id": 1,
        "campaign_name": "Summer Sale 2024",
        "platform_name": "reddit",
        "url": "https://reddit.com/r/technology/posts/abc123",
        "claimed_views": 18000,
        "claimed_clicks": 520,
        "claimed_conversions": 28,
        "reconciliation_status": "MATCHED",
        "discrepancy_level": null,
        "submitted_at": "2024-01-15T10:30:00Z",
        "last_reconciled_at": "2024-01-15T10:35:00Z"
      }
    ],
    "total": 1,
    "limit": 50,
    "offset": 0
  }
}
```

### Get Post Metrics Details
```http
GET /api/v1/submissions/{post_id}/metrics
```

**Response:**
```json
{
  "success": true,
  "data": {
    "post_id": 1,
    "affiliate_metrics": {
      "claimed_views": 18000,
      "claimed_clicks": 520,
      "claimed_conversions": 28,
      "submission_method": "API",
      "submitted_at": "2024-01-15T10:30:00Z"
    },
    "platform_metrics": {
      "observed_views": 17850,
      "observed_clicks": 495,
      "observed_conversions": 26,
      "fetched_at": "2024-01-15T10:35:00Z",
      "growth_adjustment_applied": true
    },
    "reconciliation": {
      "status": "DISCREPANCY_LOW",
      "discrepancy_level": "LOW",
      "max_discrepancy_pct": 5.2,
      "confidence_ratio": 1.0,
      "attempt_count": 1,
      "last_attempt_at": "2024-01-15T10:35:00Z"
    },
    "discrepancies": [
      {
        "metric": "views",
        "claimed": 18000,
        "observed": 17850,
        "absolute_diff": 150,
        "pct_diff": 0.84
      },
      {
        "metric": "clicks", 
        "claimed": 520,
        "observed": 495,
        "absolute_diff": 25,
        "pct_diff": 5.05
      }
    ]
  }
}
```

## Reconciliation

### Trigger Manual Reconciliation
```http
POST /api/v1/reconciliation/run
```

**Request Body:**
```json
{
  "post_id": 1,
  "force_reprocess": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Reconciliation triggered successfully",
  "data": {
    "jobs_enqueued": 1,
    "affiliate_report_ids": [1],
    "estimated_completion": "2024-01-15T10:40:00Z"
  }
}
```

### Get Reconciliation Results
```http
GET /api/v1/reconciliation/results
```

**Query Parameters:**
- `affiliate_id`: Filter by affiliate
- `status`: Filter by reconciliation status
- `discrepancy_level`: Filter by discrepancy level (LOW, MEDIUM, HIGH, CRITICAL)
- `start_date`: Filter by date range (ISO format)
- `end_date`: Filter by date range (ISO format)
- `limit`: Number of results (default: 50)

**Response:**
```json
{
  "success": true,
  "data": {
    "reconciliation_logs": [
      {
        "id": 1,
        "affiliate_report_id": 1,
        "post_id": 1,
        "affiliate_name": "John Smith",
        "campaign_name": "Summer Sale 2024",
        "platform_name": "reddit",
        "status": "DISCREPANCY_LOW",
        "discrepancy_level": "LOW",
        "max_discrepancy_pct": 5.2,
        "attempt_count": 1,
        "trust_delta": -0.01,
        "last_attempt_at": "2024-01-15T10:35:00Z"
      }
    ],
    "summary": {
      "total": 1,
      "by_status": {
        "MATCHED": 25,
        "DISCREPANCY_LOW": 8,
        "DISCREPANCY_MEDIUM": 3,
        "DISCREPANCY_HIGH": 1
      },
      "avg_confidence_ratio": 0.95
    }
  }
}
```

## Platforms

### List Available Platforms
```http
GET /api/v1/platforms/
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "reddit",
      "display_name": "Reddit",
      "is_active": true,
      "supported_metrics": ["views", "clicks", "conversions"],
      "api_status": "operational"
    },
    {
      "id": 2,
      "name": "instagram", 
      "display_name": "Instagram",
      "is_active": true,
      "supported_metrics": ["views", "clicks", "conversions"],
      "api_status": "operational"
    }
  ]
}
```

### Manual Platform Data Fetch
```http
POST /api/v1/platforms/{platform_id}/fetch
```

**Request Body:**
```json
{
  "post_url": "https://reddit.com/r/technology/posts/abc123",
  "force_refresh": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Platform data fetched successfully",
  "data": {
    "platform_name": "reddit",
    "post_url": "https://reddit.com/r/technology/posts/abc123",
    "metrics": {
      "views": 17850,
      "clicks": 495,
      "conversions": 26
    },
    "fetched_at": "2024-01-15T11:00:00Z",
    "cache_hit": false
  }
}
```

## Alerts

### Get Active Alerts
```http
GET /api/v1/alerts/
```

**Query Parameters:**
- `status`: Filter by alert status (OPEN, RESOLVED)
- `alert_type`: Filter by alert type (HIGH_DISCREPANCY, MISSING_DATA)
- `severity`: Filter by severity (LOW, MEDIUM, HIGH, CRITICAL)
- `affiliate_id`: Filter by affiliate
- `platform_id`: Filter by platform

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "alert_type": "HIGH_DISCREPANCY",
      "category": "FRAUD",
      "severity": "HIGH",
      "title": "High discrepancy detected",
      "message": "Affiliate overclaimed views by 45% on Reddit post",
      "affiliate_name": "John Smith",
      "platform_name": "reddit",
      "threshold_breached": {
        "max_discrepancy_pct": 45.2,
        "threshold": 20.0
      },
      "status": "OPEN",
      "created_at": "2024-01-15T11:15:00Z",
      "post_url": "https://reddit.com/r/technology/posts/xyz789"
    }
  ]
}
```

### Resolve Alert
```http
PUT /api/v1/alerts/{alert_id}/resolve
```

**Request Body:**
```json
{
  "resolution_notes": "Investigated with affiliate - metrics tracking issue resolved",
  "resolved_by": "admin_user_123"
}
```

## Error Codes

| Code | Description |
|------|-------------|
| `VALIDATION_ERROR` | Request validation failed |
| `AUTHENTICATION_REQUIRED` | Missing or invalid API key |
| `AUTHORIZATION_FAILED` | Insufficient permissions |
| `RESOURCE_NOT_FOUND` | Requested resource doesn't exist |
| `DUPLICATE_SUBMISSION` | Post already submitted for this campaign/platform |
| `CAMPAIGN_PLATFORM_MISMATCH` | Platform not associated with campaign |
| `RECONCILIATION_IN_PROGRESS` | Reconciliation already running for this post |
| `PLATFORM_UNAVAILABLE` | Platform integration temporarily unavailable |
| `RATE_LIMIT_EXCEEDED` | Too many requests from this API key |

## Rate Limits

- **Submissions**: 100 per hour per affiliate
- **General API**: 1000 requests per hour per API key
- **Reconciliation triggers**: 10 per minute per affiliate

Rate limit headers are included in all responses:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1610712000
```

## Webhooks (Future Feature)

The platform will support webhooks for real-time notifications:

- Reconciliation completed
- High discrepancy detected  
- Alert created
- Trust score threshold crossed

## SDK Examples

### Python SDK Usage
```python
from affiliate_platform import Client

client = Client(api_key="aff_your_api_key")

# Submit new post
post = client.submissions.create(
    campaign_id=1,
    platform_id=1,
    url="https://reddit.com/r/tech/posts/abc123",
    claimed_views=5000,
    claimed_clicks=150,
    claimed_conversions=8
)

# Check reconciliation status
status = client.reconciliation.get_status(post.id)
print(f"Status: {status.reconciliation_status}")
```

### JavaScript SDK Usage
```javascript
import { AffiliateClient } from '@affiliate-platform/sdk';

const client = new AffiliateClient({
  apiKey: 'aff_your_api_key',
  baseURL: 'https://api.affiliate-platform.com/v1'
});

// Submit new post
const post = await client.submissions.create({
  campaignId: 1,
  platformId: 1,
  url: 'https://reddit.com/r/tech/posts/abc123',
  claimedViews: 5000,
  claimedClicks: 150,
  claimedConversions: 8
});

// Get submission history
const history = await client.submissions.getHistory({
  limit: 20,
  status: 'MATCHED'
});
```

---

For more details on system architecture and implementation, see:
- [Architecture Overview](ARCHITECTURE_OVERVIEW.md)
- [Data Model Documentation](DATA_MODEL.md)
- [Integration Development Guide](INTEGRATIONS.md)