# Configuration Reference

Complete reference for configuring the Affiliate Reconciliation Platform.

## Configuration Files

The platform uses multiple configuration sources in order of precedence:

1. **Environment Variables** (highest priority)
2. **`.env` file** (local development)
3. **`app/config.py`** (application defaults)
4. **Database configuration** (runtime platform settings)

## Environment Variables

### Core Application Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./test.db` | Database connection string |
| `SECRET_KEY` | (required) | Secret key for session/JWT signing |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `LOG_FILE` | `logs/app.log` | Log file path |
| `CORS_ORIGINS` | `*` | Comma-separated list of allowed CORS origins |

### Integration Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `INTEGRATIONS_RANDOM_SEED` | `None` | Random seed for consistent mock data (testing) |
| `MOCK_FAILURE_RATE` | `0.05` | Simulated failure rate for mock integrations (5%) |
| `REDDIT_LINK_RESOLVE_TIMEOUT` | `10` | Timeout for Reddit URL resolution (seconds) |

### Platform API Keys (Production)

| Variable | Description |
|----------|-------------|
| `REDDIT_CLIENT_ID` | Reddit API client ID |
| `REDDIT_CLIENT_SECRET` | Reddit API client secret |
| `REDDIT_USER_AGENT` | Reddit API user agent string |
| `INSTAGRAM_ACCESS_TOKEN` | Instagram Graph API access token |
| `TIKTOK_ACCESS_TOKEN` | TikTok Business API access token |
| `YOUTUBE_API_KEY` | YouTube Data API v3 key |
| `TWITTER_BEARER_TOKEN` | X/Twitter API v2 bearer token |

### Development Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVELOPMENT_MODE` | `False` | Enable development features |
| `DISABLE_WORKER` | `False` | Disable background reconciliation worker |
| `ENABLE_DEBUG_ENDPOINTS` | `False` | Enable debug/admin endpoints |

### Discord Bot Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_DISCORD_BOT` | `false` | Enable Discord bot integration |
| `DISCORD_BOT_TOKEN` | (none) | Discord bot authentication token |
| `DISCORD_COMMAND_GUILDS` | (empty) | Comma-separated guild IDs for faster command registration |
| `API_BASE_URL` | `http://localhost:8000/api/v1` | Base URL for the FastAPI service |
| `BOT_INTERNAL_TOKEN` | (none) | Internal token for bot-submitted requests |

## Application Configuration (`app/config.py`)

### Reconciliation Engine Settings

```python
RECONCILIATION_SETTINGS = {
    # Base tolerance BEFORE growth allowance. Diff within this is a match.
    "base_tolerance_pct": 0.05,  # 5%
    
    # Discrepancy tier thresholds (upper bounds). > medium_max => HIGH.
    "discrepancy_tiers": {
        "low_max": 0.10,     # 10%
        "medium_max": 0.20,  # 20%
    },
    
    # Overclaim threshold: affiliate significantly above platform.
    "overclaim_threshold_pct": 0.20,   # 20%
    "overclaim_critical_pct": 0.50,    # 50% triggers CRITICAL alert
    
    # Allowance for organic growth between submission & fetch.
    "growth_per_hour_pct": 0.10,       # 10% per hour
    "growth_cap_hours": 24,            # Cap growth adjustment window
}
```

### Trust Scoring Configuration

```python
TRUST_SCORING = {
    # Trust score boundaries
    "min_score": 0.0,                # Minimum possible trust score
    "max_score": 1.0,                # Maximum possible trust score
    
    # Trust event deltas (additive adjustments, not percentages)
    "events": {
        "perfect_match": +0.01,       # Bonus for perfect match
        "minor_discrepancy": -0.01,  # Small penalty for minor issues
        "medium_discrepancy": -0.03, # Medium penalty
        "high_discrepancy": -0.05,   # High penalty
        "overclaim": -0.10,          # Severe penalty for overclaiming
        "impossible_submission": -0.15  # Critical penalty for impossible claims
    },
    
    # Thresholds for operational behaviors
    "reduced_frequency_threshold": 0.75,    # High trust threshold
    "increased_monitoring_threshold": 0.50, # Normal threshold  
    "manual_review_threshold": 0.25         # Low trust threshold
}
```

### Retry Policy Configuration

```python
RETRY_POLICY = {
    # Missing platform data retry settings
    "missing_platform_data": {
        "initial_delay_minutes": 30,  # First retry after 30 minutes
        "max_attempts": 5,            # Maximum retry attempts
        "window_hours": 24            # Give up after 24 hours
    },
    
    # Partial data retry settings
    "incomplete_platform_data": {
        "max_additional_attempts": 1  # Allow one additional attempt
    }
}
```

### Queue Configuration

```python
QUEUE_SETTINGS = {
    # Priority levels (lower number = higher priority)
    "priorities": {
        "high": 0,     # Urgent/suspicious submissions
        "normal": 5,   # Standard submissions
        "low": 10      # Backfill/retry submissions
    },
    
    # Queue management
    "warn_depth": 1000,      # Log warning when queue exceeds this size
    "max_in_memory": 5000    # Maximum jobs in memory queue
}
```

### Alerting Configuration

```python
ALERTING_SETTINGS = {
    # Alert escalation timeouts
    "platform_down_escalation_minutes": 120,  # Escalate platform issues after 2 hours
    "repeat_overclaim_window_hours": 6         # Window for repeat offense detection
}
```

### Data Quality Settings

```python
DATA_QUALITY_SETTINGS = {
    # Ratio thresholds for suspicious activity detection
    "max_ctr_pct": 0.35,              # clicks/views > 35% suspicious
    "max_cvr_pct": 0.60,              # conversions/clicks > 60% suspicious
    
    # Growth/spike detection thresholds
    "max_views_growth_pct": 5.0,      # >500% vs previous report views
    "max_clicks_growth_pct": 5.0,     # >500% vs previous report clicks
    "max_conversions_growth_pct": 5.0,# >500% vs previous report conversions
    
    # Evidence requirement thresholds
    "evidence_required_views": 50000, # Require evidence for claims >50k views
    
    # Non-monotonic allowances (allow small negative noise)
    "monotonic_tolerance": 0.01,      # 1% tolerance for small decreases
    
    # Minimum baseline to evaluate certain ratios
    "min_views_for_ctr": 100,         # Minimum views to evaluate CTR
    "min_clicks_for_cvr": 20          # Minimum clicks to evaluate CVR
}
```

### Circuit Breaker Configuration

```python
CIRCUIT_BREAKER_SETTINGS = {
    # Failure thresholds
    "failure_threshold": 5,          # Failures before opening circuit
    "recovery_timeout": 60,          # Seconds before attempting recovery
    "open_cooldown_seconds": 300,    # Cooldown period when circuit is open
    "half_open_probe_count": 3       # Test calls when half-open
}
```

### Backoff Policy Configuration

```python
BACKOFF_POLICY = {
    # Exponential backoff settings for failed operations
    "base_seconds": 1,               # Base delay in seconds
    "factor": 2,                     # Exponential factor
    "max_seconds": 60,               # Maximum delay
    "max_attempts": 3,               # Maximum retry attempts
    "jitter_pct": 0.10               # Random jitter (+/-10%)
}
```

## Database Configuration

### Connection Settings

**SQLite (Development):**
```python
DATABASE_URL = "sqlite:///./test.db"
```

**PostgreSQL (Production):**
```python
DATABASE_URL = "postgresql://user:password@host:port/database"

# Connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=20,          # Number of connections to maintain
    max_overflow=30,       # Additional connections when pool is full
    pool_pre_ping=True,    # Validate connections before use
    pool_recycle=3600      # Recycle connections after 1 hour
)
```

### Performance Tuning

**Recommended PostgreSQL settings for production:**

```sql
-- Memory settings
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 64MB

-- Connection settings
max_connections = 100

-- WAL settings
wal_buffers = 16MB
checkpoint_completion_target = 0.7

-- Query planner
random_page_cost = 1.1
effective_io_concurrency = 200
```

**Recommended indexes:**
```sql
-- Performance indexes
CREATE INDEX idx_posts_affiliate_campaign ON posts(affiliate_id, campaign_id);
CREATE INDEX idx_reconciliation_logs_status ON reconciliation_logs(status);
CREATE INDEX idx_affiliate_reports_submitted_at ON affiliate_reports(submitted_at);
CREATE INDEX idx_alerts_created_at ON alerts(created_at) WHERE status = 'OPEN';
```

## Runtime Configuration

### Platform-Specific Settings

Platform configurations can be updated via API and are stored in the database:

```json
{
  "reddit": {
    "api_base_url": "https://oauth.reddit.com",
    "rate_limit": 60,
    "timeout": 30,
    "retry_attempts": 3,
    "use_mock": true
  },
  "instagram": {
    "api_base_url": "https://graph.instagram.com",
    "api_version": "v18.0",
    "rate_limit": 200,
    "timeout": 30,
    "retry_attempts": 3,
    "use_mock": true
  }
}
```

### Campaign Settings

Campaign-specific reconciliation rules:

```json
{
  "campaign_id": 1,
  "reconciliation_frequency": "immediate",
  "custom_thresholds": {
    "base_tolerance": 3.0,
    "high_threshold": 25.0
  },
  "growth_allowance_multiplier": 1.5,
  "priority_boost": false
}
```

### Affiliate Settings

Affiliate-specific configuration:

```json
{
  "affiliate_id": 1,
  "trust_score_multiplier": 1.0,
  "custom_priority": null,
  "monitoring_level": "standard",
  "rate_limit_override": null
}
```

## Configuration Examples

### Development Environment

**.env file:**
```bash
# Development settings
DATABASE_URL=sqlite:///./dev.db
LOG_LEVEL=DEBUG
LOG_FILE=logs/dev.log
DEVELOPMENT_MODE=true

# Consistent mock data for testing
INTEGRATIONS_RANDOM_SEED=12345
MOCK_FAILURE_RATE=0.1

# CORS for frontend development
CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# Discord bot (optional)
ENABLE_DISCORD_BOT=true
DISCORD_BOT_TOKEN=your_dev_bot_token
DISCORD_COMMAND_GUILDS=123456789012345678
API_BASE_URL=http://localhost:8000/api/v1
BOT_INTERNAL_TOKEN=dev-internal-token

# Secret key (generate new for production)
SECRET_KEY=dev-secret-key-change-in-production
```

### Production Environment

**.env file:**
```bash
# Production database
DATABASE_URL=postgresql://affiliate_user:secure_password@db:5432/affiliate_reconciliation

# Production logging
LOG_LEVEL=INFO
LOG_FILE=/app/logs/app.log

# Security
SECRET_KEY=your-very-secure-secret-key
CORS_ORIGINS=https://yourdomain.com,https://admin.yourdomain.com

# Real platform APIs
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
INSTAGRAM_ACCESS_TOKEN=your_instagram_token
YOUTUBE_API_KEY=your_youtube_api_key
TWITTER_BEARER_TOKEN=your_twitter_token

# Discord bot (optional)
ENABLE_DISCORD_BOT=true
DISCORD_BOT_TOKEN=your_prod_bot_token
API_BASE_URL=https://yourdomain.com/api/v1
BOT_INTERNAL_TOKEN=your-secure-internal-token

# Production settings
MOCK_FAILURE_RATE=0.0
REDDIT_LINK_RESOLVE_TIMEOUT=5
```

### Testing Environment

**.env.test file:**
```bash
# Test database (in-memory)
DATABASE_URL=sqlite:///:memory:

# Test logging
LOG_LEVEL=WARNING
LOG_FILE=/dev/null

# Deterministic test data
INTEGRATIONS_RANDOM_SEED=42
MOCK_FAILURE_RATE=0.0

# Fast timeouts for tests
REDDIT_LINK_RESOLVE_TIMEOUT=1

# Disable background worker for tests
DISABLE_WORKER=true
```

## Configuration Validation

The platform validates configuration on startup:

```python
def validate_config():
    """Validate critical configuration settings."""
    
    # Required settings
    if not os.getenv("SECRET_KEY"):
        raise ValueError("SECRET_KEY environment variable is required")
    
    # Database URL format
    db_url = os.getenv("DATABASE_URL")
    if not db_url or not db_url.startswith(("sqlite://", "postgresql://")):
        raise ValueError("Invalid DATABASE_URL format")
    
    # Trust scoring bounds
    if TRUST_SCORING["min_score"] >= TRUST_SCORING["max_score"]:
        raise ValueError("Invalid trust score boundaries")
    
    # Threshold ordering
    thresholds = RECONCILIATION_SETTINGS
    if not (thresholds["base_tolerance"] < thresholds["low_threshold"] < 
            thresholds["medium_threshold"] < thresholds["high_threshold"]):
        raise ValueError("Reconciliation thresholds must be in ascending order")
```

## Configuration Updates

### Runtime Updates via API

Some configurations can be updated at runtime:

```http
PUT /api/v1/admin/config
Authorization: Bearer admin_token
Content-Type: application/json

{
  "trust_scoring": {
    "events": {
      "OVERCLAIM": -0.15
    }
  },
  "reconciliation": {
    "base_tolerance": 3.0
  }
}
```

### Database Configuration Migration

For production config changes:

```sql
-- Update platform configuration
UPDATE platforms 
SET config = jsonb_set(config, '{rate_limit}', '1000') 
WHERE name = 'reddit';

-- Update global settings
INSERT INTO system_config (key, value, updated_at) 
VALUES ('reconciliation.base_tolerance', '3.0', NOW())
ON CONFLICT (key) 
DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();
```

### Configuration Monitoring

Monitor configuration changes:

```python
@app.on_event("startup")
async def log_configuration():
    """Log current configuration on startup."""
    logger.info("Configuration loaded", 
                database_url=DATABASE_URL,
                log_level=LOG_LEVEL,
                mock_failure_rate=MOCK_FAILURE_RATE,
                queue_priorities=QUEUE_SETTINGS["priorities"])
```

## Security Considerations

### Sensitive Data Protection

- **Never commit `.env` files** containing production secrets
- **Use environment-specific `.env` files** (`.env.prod`, `.env.staging`)
- **Rotate secrets regularly** (API keys, database passwords)
- **Use secrets management** (AWS Secrets Manager, HashiCorp Vault) in production

### Configuration Validation

- **Validate on startup** to catch misconfigurations early
- **Use type hints** for configuration objects
- **Document required vs optional** settings
- **Provide sensible defaults** for development

### Access Control

- **Limit configuration updates** to admin users only
- **Audit configuration changes** with timestamps and user tracking
- **Validate configuration changes** before applying
- **Support rollback** for configuration changes

For deployment-specific configuration guidance, see [Setup Guide](SETUP_GUIDE.md).