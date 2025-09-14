# API Reference

Complete reference for all REST API endpoints in the Affiliate Reconciliation Platform.

## Base URL
```
http://localhost:8000/api/v1
```

## Authentication
All API endpoints require authentication via Bearer token:
```
Authorization: Bearer {api_key}
```

API keys are generated when creating a user account and returned in the response.

### Role-Based Access Control (RBAC)
The platform implements role-based access control with the following user roles:

- **AFFILIATE**: Can submit posts, view their own submissions, and access basic platform information
- **CLIENT**: Can access reconciliation data, trigger reconciliations, and manage campaigns  
- **ADMIN**: Full system access including user management and system administration

Some endpoints require specific roles and will return `403 Forbidden` if accessed by users without sufficient permissions.

## Users

### Create User
```http
POST /api/v1/users/
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
  "message": "User created successfully",
  "data": {
    "id": 1,
    "name": "John Smith",
    "email": "john@example.com",
    "api_key": "user_abc123def456",
    "trust_score": 0.50,
    "role": "AFFILIATE",
    "is_active": true,
    "created_at": "2024-01-15T10:30:00Z"
  }
}


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

## Analytics

### Get Campaign Analytics
```http
GET /api/v1/analytics/campaigns/{campaign_id}
```

Return essential metrics for a single campaign (MVP scope only).

RBAC:
* ADMIN: access any campaign
* CLIENT: only campaigns with matching `client_id`
* AFFILIATE: 403 Forbidden

**Response:**
```json
{
  "campaign_id": 123,
  "campaign_name": "Spring Promo",
  "client_id": 42,
  "totals": {"posts": 18, "views": 4567, "clicks": 321, "conversions": 44},
  "reconciliation": {"success_rate": 0.8753, "pending_reports": 5, "total_reconciled": 40},
  "platform_breakdown": [
    {"platform_id": 1, "platform_name": "reddit", "views": 2000, "clicks": 120, "conversions": 10},
    {"platform_id": 2, "platform_name": "instagram", "views": 2567, "clicks": 201, "conversions": 34}
  ],
  "recent_alerts": [
    {"id": 9, "severity": "HIGH", "status": "OPEN", "title": "Overclaim detected", "created_at": "2025-09-13T10:22:55Z"}
  ],
  "request_id": "..."
}
```

Notes:
* Success statuses counted toward success_rate: `MATCHED`, `DISCREPANCY_LOW`.
* `success_rate` is null when there are zero reconciled reports.
* `recent_alerts` limited to most recent 5 alerts tied to campaign via reconciliation logs.
* No date filtering yet (future enhancement).

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

### Get Post Metrics History
```http
GET /api/v1/submissions/{post_id}/metrics
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
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
  ]
}
```

## Reconciliation

**Access Control**: All reconciliation endpoints require **ADMIN** or **CLIENT** role.

### Trigger Manual Reconciliation
```http
POST /api/v1/reconciliation/run
```

**Required Role**: ADMIN or CLIENT

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

**Required Role**: ADMIN or CLIENT

**Query Parameters:**
- `user_id`: Filter by user (replaces affiliate_id)
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
        "user_name": "John Smith",
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

### Get Reconciliation Queue Status
```http
GET /api/v1/reconciliation/queue
```

**Required Role**: ADMIN or CLIENT

**Response:**
```json
{
  "success": true,
  "message": "Queue snapshot",
  "data": {
    "snapshot": {
      "depth": 5,
      "ready": 3,
      "scheduled": 2,
      "shutdown": false,
      "redis_active": true,
      "redis_url": "redis://localhost:6379/0"
    },
    "request_id": "req_abc123"
  }
}
```

### Get Specific Reconciliation Result
```http
GET /api/v1/reconciliation/logs/{affiliate_report_id}
```

**Required Role**: ADMIN or CLIENT

**Response:**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "affiliate_report_id": 1,
    "platform_report_id": 2,
    "status": "DISCREPANCY_LOW",
    "discrepancy_level": "LOW",
    "views_discrepancy": 150,
    "clicks_discrepancy": 25,
    "conversions_discrepancy": 3,
    "views_diff_pct": 0.84,
    "clicks_diff_pct": 5.05,
    "conversions_diff_pct": 10.0,
    "notes": "Minor discrepancy detected",
    "processed_at": "2024-01-15T10:35:00Z",
    "affiliate_metrics": {
      "views": 18000,
      "clicks": 520,
      "conversions": 28,
      "post_url": "https://reddit.com/r/technology/posts/abc123",
      "platform_name": "reddit",
      "timestamp": "2024-01-15T10:30:00Z",
      "source": "user_claim"
    },
    "platform_metrics": {
      "views": 17850,
      "clicks": 495,
      "conversions": 26,
      "post_url": "https://reddit.com/r/technology/posts/abc123",
      "platform_name": "reddit",
      "timestamp": "2024-01-15T10:35:00Z",
      "source": "platform_api"
    },
    "discrepancies": [
      {
        "metric": "views",
        "claimed": 18000,
        "observed": 17850,
        "absolute_diff": 150,
        "pct_diff": 0.84
      }
    ],
    "max_discrepancy_pct": 10.0,
    "trust_change": {
      "event": "minor_discrepancy",
      "previous": 0.85,
      "new": 0.83,
      "delta": -0.02
    },
    "job": {
      "attempt_count": 1,
      "max_attempts": 3,
      "next_retry_at": null,
      "queue_priority": "normal"
    },
    "meta": {}
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

### Get Alert Statistics
```http
GET /api/v1/alerts/stats
```

**Response:**
```json
{
  "success": true,
  "data": {
    "total_alerts": 45,
    "by_status": {
      "OPEN": 12,
      "RESOLVED": 33
    },
    "by_type": {
      "HIGH_DISCREPANCY": 18,
      "MISSING_DATA": 15,
      "TRUST_THRESHOLD": 12
    },
    "recent_24h": 8,
    "generated_at": "2024-01-15T11:30:00Z"
  }
}
```

## Clients

### Create Client (Admin Only)
```http
POST /api/v1/clients/
```

**Request Body:**
```json
{
  "name": "TechCorp Inc",
  "contact_email": "admin@techcorp.com",
  "contact_name": "Jane Smith",
  "description": "Technology marketing client"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Client created successfully",
  "data": {
    "id": 1,
    "name": "TechCorp Inc",
    "contact_email": "admin@techcorp.com",
    "contact_name": "Jane Smith",
    "description": "Technology marketing client",
    "is_active": true,
    "created_at": "2024-01-15T10:30:00Z",
    "user_count": 0
  }
}
```

### List Clients (Admin Only)
```http
GET /api/v1/clients/
```

**Query Parameters:**
- `skip`: Number of clients to skip (default: 0)
- `limit`: Number of clients to return (default: 100)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "TechCorp Inc",
      "contact_email": "admin@techcorp.com",
      "contact_name": "Jane Smith",
      "is_active": true,
      "user_count": 5,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### Get Client Details (Admin Only)
```http
GET /api/v1/clients/{client_id}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "name": "TechCorp Inc",
    "contact_email": "admin@techcorp.com",
    "contact_name": "Jane Smith",
    "description": "Technology marketing client",
    "is_active": true,
    "created_at": "2024-01-15T10:30:00Z",
    "users": [
      {
        "id": 2,
        "name": "John Affiliate",
        "email": "john@techcorp.com",
        "role": "AFFILIATE",
        "is_active": true
      }
    ],
    "campaigns": [
      {
        "id": 1,
        "name": "Summer Sale 2024",
        "status": "ACTIVE",
        "start_date": "2024-06-01",
        "end_date": "2024-08-31"
      }
    ]
  }
}
```

### Update Client (Admin Only)
```http
PUT /api/v1/clients/{client_id}
```

**Request Body:**
```json
{
  "name": "TechCorp Solutions Inc",
  "contact_email": "newadmin@techcorp.com",
  "contact_name": "John Doe",
  "description": "Updated technology marketing client"
}
```

### Delete Client (Admin Only)
```http
DELETE /api/v1/clients/{client_id}
```

**Response:**
```json
{
  "success": true,
  "message": "Client deleted successfully"
}
```

## Error Codes

| Code | Description |
|------|-------------|
| `VALIDATION_ERROR` | Request validation failed |
| `AUTHENTICATION_REQUIRED` | Missing or invalid API key |
| `AUTHORIZATION_FAILED` | Insufficient permissions for the requested operation |
| `RESOURCE_NOT_FOUND` | Requested resource doesn't exist |
| `DUPLICATE_SUBMISSION` | Post already submitted for this campaign/platform |
| `CAMPAIGN_PLATFORM_MISMATCH` | Platform not associated with campaign |
| `RECONCILIATION_IN_PROGRESS` | Reconciliation already running for this post |
| `PLATFORM_UNAVAILABLE` | Platform integration temporarily unavailable |
| `RATE_LIMIT_EXCEEDED` | Too many requests from this API key |

## Rate Limits

The platform enforces per-API key limits with endpoint categories. Defaults (can be overridden via environment variables):

| Category | Default Limit | Window | Description |
|----------|---------------|--------|-------------|
| `default` | 1000 | 1 hour | All requests not in a more specific category |
| `submission` | 100 | 1 hour | Post submissions & metric updates (`/api/v1/submissions`) |
| `recon_trigger` | 10 | 60 seconds | Manual reconciliation trigger (`POST /api/v1/reconciliation/run`) |
| `recon_query` | 100 | 60 seconds | Reconciliation result/query endpoints (`/api/v1/reconciliation/results`, `/logs/{id}`, `/queue`) |

Role-based overrides (for the `default` category) may increase limits for privileged users (e.g. ADMIN 5000, CLIENT 2000) if configured.

Environment variable knobs (examples):
```
RATE_LIMIT_DEFAULT_LIMIT=1000
RATE_LIMIT_DEFAULT_WINDOW=3600
RATE_LIMIT_SUBMISSION_LIMIT=100
RATE_LIMIT_RECON_TRIGGER_LIMIT=10
RATE_LIMIT_RECON_TRIGGER_WINDOW=60
RATE_LIMIT_RECON_QUERY_LIMIT=100
RATE_LIMIT_ROLE_ADMIN_LIMIT=5000
```

Standard headers are returned on every response:
```
X-RateLimit-Limit: <int total allowed in window>
X-RateLimit-Remaining: <int remaining>
X-RateLimit-Reset: <epoch seconds when window resets>
```

If the limit is exceeded a `429 Too Many Requests` response is returned with body:
```json
{
  "success": false,
  "message": "Rate limit exceeded for category 'submission'",
  "category": "submission"
}
```

## Webhooks (Future Feature)

The platform will support webhooks for real-time notifications:

- Reconciliation completed
- High discrepancy detected  
- Alert created
- Trust score threshold crossed

---

For more details on system architecture and implementation, see:
- [Architecture Overview](ARCHITECTURE_OVERVIEW.md)
- [Data Model Documentation](DATA_MODEL.md)
- [Integration Development Guide](INTEGRATIONS.md)