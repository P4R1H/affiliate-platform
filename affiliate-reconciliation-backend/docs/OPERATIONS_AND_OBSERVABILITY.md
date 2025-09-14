# Operations & Observability Runbook

Guidance for running, monitoring, and troubleshooting the reconciliation platform.

## 1. Operational Objectives
| Objective | Description |
|----## 6. Health Checks & Monitoring

**File**: `app/main.py`
## 8. Circuit Breaker Runbook

**File**: `app/utils/circuit_breaker.py`

The platform includes an in-memory circuit breaker for protecting against cascading failures in platform integration## 10. Troubleshooting Guide

| Issue | Likely Causes | Steps |
|-------|---------------|-------|
| **All reconciliations become MISSING** | Platform outage, circuit breaker open, adapter import error | 1. Check logs for `fetch_error` vs `circuit_open` patterns<br>2. Verify platform API status manually<br>3. Check circuit breaker state: `GLOBAL_CIRCUIT_BREAKER.snapshot()`<br>4. Validate adapter module imports |
| **Trust scores plummet globally** | Misconfigured thresholds / growth allowance | 1. Inspect `RECONCILIATION_SETTINGS` in config<br>2. Run trust scoring unit tests with boundary values<br>3. Check recent trust events in logs<br>4. Verify growth allowance calculations |
| **Alert flood (overclaim)** | Real fraud wave or adapter returning low metrics | 1. Sample recent PlatformReport entries vs affiliate claims<br>2. Check alert creation logs for patterns<br>3. Verify platform adapter metric accuracy<br>4. Review discrepancy calculation logic |
| **Queue depth climbs** | Worker stalled, long fetch times, high submission volume | 1. Check worker logs for processing messages<br>2. Monitor platform fetch timing in performance logs<br>3. Verify worker thread is alive<br>4. Check database connection pool status |
| **Reconciliation log updates failing** | DB schema drift / migrations | 1. Check database connection and transaction logs<br>2. Verify SQLAlchemy model definitions match DB schema<br>3. Check for database constraint violations<br>4. Review recent schema changes |
| **High latency on submissions** | Database slow queries, external API delays | 1. Check `X-Process-Time` headers in responses<br>2. Monitor database query performance<br>3. Profile platform API response times<br>4. Check for N+1 query patterns |
| **Circuit breaker flapping** | Intermittent platform issues | 1. Review circuit breaker configuration<br>2. Check platform API error patterns<br>3. Adjust `failure_threshold` or `open_cooldown_seconds`<br>4. Monitor breaker state transitions |
| **Worker exceptions accumulating** | Code bugs, external service failures | 1. Check `LAST_EXCEPTIONS` in worker module<br>2. Review worker error logs with full stack traces<br>3. Test reconciliation logic with failing scenarios<br>4. Check database connectivity from worker |

### Debug Commands

```bash
# Check application health
curl http://localhost:8000/health/detailed

# Check circuit breaker state (if debug endpoint added)
curl http://localhost:8000/debug/circuit-breakers

# Monitor logs in real-time
tail -f logs/app.log | jq '.message'

# Check worker status
ps aux | grep reconciliation-worker

# Database connection test
python -c "from app.database import SessionLocal; db = SessionLocal(); db.execute('SELECT 1'); print('DB OK')"
```

### Log Analysis Patterns

```bash
# Find reconciliation failures
grep "Reconciliation job failed" logs/app.log

# Check platform fetch performance
grep "Performance: platform_fetch" logs/app.log | jq '.duration_ms'

# Monitor circuit breaker state changes
grep "circuit_" logs/app.log

# Find request correlation
grep "request_id.*123e4567" logs/app.log
```

## 11. Incident Response Playbook (Abbreviated)# Circuit Breaker States

- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Failure threshold exceeded, requests fail fast
- **HALF_OPEN**: Testing recovery, limited requests allowed

### Configuration

```python
# From app/config.py
CIRCUIT_BREAKER = {
    "failure_threshold": 5,        # Failures before opening
    "open_cooldown_seconds": 60,   # Time before half-open
    "half_open_probe_count": 3,    # Requests in half-open state
}
```

### Monitoring Circuit Breaker State

```python
from app.utils.circuit_breaker import GLOBAL_CIRCUIT_BREAKER

# Get snapshot of all breaker states
snapshot = GLOBAL_CIRCUIT_BREAKER.snapshot()
print(snapshot)
# Output: {
#   "reddit": {
#     "failures": 0,
#     "state": "CLOSED",
#     "opened_at": None,
#     "half_open_probes": 0
#   },
#   "instagram": {
#     "failures": 2,
#     "state": "CLOSED",
#     "opened_at": None,
#     "half_open_probes": 0
#   }
# }
```

### Diagnostic Endpoint (Future)

Consider adding an API endpoint to expose breaker states:

```python
@app.get("/debug/circuit-breakers")
async def circuit_breaker_status():
    """Debug endpoint for circuit breaker monitoring."""
    return GLOBAL_CIRCUIT_BREAKER.snapshot()
```

### Troubleshooting Circuit Breaker Issues

| Symptom | Action |
|---------|--------|
| Frequent `circuit_open` warnings | Confirm upstream platform API availability; consider raising threshold temporarily |
| Rapid OPEN ↔ HALF_OPEN flapping | Increase `open_cooldown_seconds` or reduce `half_open_probe_count` |
| High missing due to breaker | Add missing_reason instrumentation to differentiate true missing |atform provides comprehensive health check endpoints for load balancers and monitoring systems.

### Basic Health Check

**Endpoint**: `GET /health`

Returns basic health status for load balancer checks:

```json
{
  "status": "healthy",
  "service": "affiliate-reconciliation-platform",
  "version": "1.0.0",
  "timestamp": 1703123456.789
}
```

### Detailed Health Check

**Endpoint**: `GET /health/detailed`

Performs comprehensive system checks:

```json
{
  "status": "healthy",
  "service": "affiliate-reconciliation-platform",
  "version": "1.0.0",
  "timestamp": 1703123456.789,
  "checks": {
    "database": "healthy"
  }
}
```

**Checks Performed**:
- **Database Connectivity**: Tests database connection and basic query execution
- **Future Checks**: Redis, external APIs, file system, queue health

### Health Check Configuration

Health checks can be extended to monitor:
- Queue depth and worker status
- Circuit breaker states
- External service dependencies
- Disk space and system resources
- Platform API rate limits

## 7. Circuit Breaker Runbook-----------|
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

## 3. Logging Infrastructure

The platform uses a comprehensive structured logging system with JSON formatting for production and human-readable formatting for development.

### Logger Configuration

**File**: `app/utils/logger.py`

**Features**:
- **JSONFormatter**: Structured JSON logging for production with timestamps, levels, and metadata
- **StructuredLogger**: Wrapper class providing typed logging methods with extra data support
- **RotatingFileHandler**: Automatic log rotation (10MB files, 5 backups)
- **Multi-handler Support**: Console + file logging with different formats

**Setup**:
```python
from app.utils import setup_logging, get_logger

# Setup logging (called in main.py)
setup_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_file=os.getenv("LOG_FILE", "logs/app.log"),
    enable_console=True
)

# Get structured logger
logger = get_logger(__name__)
```

### Structured Logging Methods

```python
# Info with structured data
logger.info(
    "Reconciliation completed",
    report_id=123,
    status="MATCHED",
    duration_ms=150.5
)

# Error with exception info
logger.error(
    "Platform fetch failed",
    platform="reddit",
    error=str(e),
    exc_info=True
)

# Warning with additional context
logger.warning(
    "Rate limit exceeded",
    platform="instagram",
    retry_after=60
)
```

### Log Patterns & Conventions

| Logger Pattern | Example | Purpose |
|----------------|---------|---------|
| `app.app.api.*` | `Request started` | HTTP request lifecycle |
| `app.app.jobs.worker_reconciliation` | `Processing reconciliation job` | Background worker activity |
| `app.app.services.platform_fetcher` | `Platform fetch retry scheduled` | Integration stability |
| `app.app.services.alerting` | `Created overclaim alert` | Risk events |
| `app.performance` | `Performance: submit_new_post` | Operation timing |
| `app.audit` | `Business event: affiliate_submission` | Audit trails |

### Log Fields

Common structured fields included in logs:
- `timestamp`: ISO 8601 UTC timestamp
- `level`: Log level (INFO, WARNING, ERROR)
- `logger`: Logger name
- `message`: Human-readable message
- `module`: Python module name
- `function`: Function name
- `line`: Line number
- `process_id`: Process ID
- `thread_id`: Thread ID
- Platform-specific: `platform`, `attempt`, `backoff_seconds`, `error_code`, `severity`
- Request-specific: `request_id`, `method`, `url`, `status_code`, `process_time_ms`

## 4. Request Correlation & Tracing

**File**: `app/utils/observability.py`

The platform implements comprehensive request correlation for end-to-end tracing:

### Request ID Tracking

```python
REQUEST_ID_HEADER = "X-Request-ID"

def ensure_request_id(headers: Mapping[str, str]) -> str:
    """Extract or generate request ID for tracing."""
    return headers.get(REQUEST_ID_HEADER, None) or str(uuid.uuid4())
```

### Middleware Implementation

**File**: `app/main.py`

All HTTP requests are automatically tracked with:
- **Request ID Generation**: Auto-generated UUID if not provided
- **Timing Measurement**: Request processing time in milliseconds
- **Security Headers**: XSS protection, content type options, frame options
- **Structured Logging**: Request start/completion with full context

**Request Flow**:
1. Extract or generate `X-Request-ID`
2. Log request start with method, URL, user agent, remote IP
3. Process request with timing
4. Add response headers (`X-Request-ID`, `X-Process-Time`)
5. Log request completion with status code and timing

**Response Headers Added**:
```
X-Request-ID: 123e4567-e89b-12d3-a456-426614174000
X-Process-Time: 45.67
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
```

### Business Event Auditing

**File**: `app/utils/logger.py`

Critical business events are logged for audit trails:

```python
def log_business_event(
    event_type: str,
    details: Dict[str, Any],
    user_id: Optional[int] = None,
    request_id: Optional[str] = None
) -> None:
    """Log business events for compliance and debugging."""
    # Examples: affiliate_submission, reconciliation_completed, alert_created
```

### Performance Logging

**File**: `app/utils/logger.py`

Operation performance is tracked for optimization:

```python
def log_performance(
    operation: str,
    duration_ms: float,
    additional_data: Optional[Dict[str, Any]] = None
) -> None:
    """Log performance metrics for monitoring."""
    # Examples: submit_new_post, platform_fetch, reconciliation_attempt
```

## 5. Suggested Metrics (Future Implementation)
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

## 7. Middleware & Request Processing

**File**: `app/main.py`

The platform includes comprehensive middleware for security, performance, and observability.

### Security Middleware

**Automatic Security Headers**:
```python
# Added to all responses
response.headers["X-Content-Type-Options"] = "nosniff"
response.headers["X-Frame-Options"] = "DENY"
response.headers["X-XSS-Protection"] = "1; mode=block"
```

### Performance Middleware

**GZip Compression**:
```python
app.add_middleware(GZipMiddleware, minimum_size=1000)
```
- Compresses responses larger than 1KB
- Reduces bandwidth and improves response times

### Request Processing Middleware

**Comprehensive Request Tracking**:
- **Request ID**: Auto-generated or extracted from `X-Request-ID` header
- **Timing**: Measures processing time in milliseconds
- **Logging**: Structured logging of request start/completion
- **Security**: Validates and sanitizes request data

**Middleware Flow**:
1. Extract/generate request ID
2. Log request details (method, URL, user agent, IP)
3. Start timing measurement
4. Process request through application
5. Add response headers (request ID, processing time, security headers)
6. Log completion with status code and timing

### Error Handling Middleware

**Global Exception Handlers**:
- **ValidationError**: Pydantic validation failures
- **HTTPException**: FastAPI HTTP exceptions
- **Exception**: Unexpected errors with full stack traces

All errors include:
- Request ID for correlation
- Structured logging with context
- Appropriate HTTP status codes
- Sanitized error messages for security

## 8. Worker Observability

**File**: `app/jobs/worker_reconciliation.py`

The background worker includes comprehensive observability features for monitoring and debugging.

### Worker Lifecycle Logging

```python
# Worker startup
logger.info("Reconciliation worker started")

# Job processing
logger.info("Processing reconciliation job", report_id=job.affiliate_report_id)

# Job completion
logger.info("Reconciliation completed", report_id=job.affiliate_report_id, status=result.get("status"))

# Worker shutdown
logger.info("Reconciliation worker stop requested")
```

### Exception Tracking for Debugging

**Debug Exception Store**:
```python
# Global exception tracking for testing/debugging
LAST_EXCEPTIONS: list[dict] = []

# In exception handler
LAST_EXCEPTIONS.append({
    "report_id": job.affiliate_report_id,
    "error": str(e),
    "type": type(e).__name__,
})
```

**Usage in Tests**:
```python
from app.jobs.worker_reconciliation import LAST_EXCEPTIONS

# Check for worker exceptions in test
assert len(LAST_EXCEPTIONS) == 0, f"Worker exceptions: {LAST_EXCEPTIONS}"
```

### Worker Monitoring Points

- **Job Queue Polling**: Logs when checking for new jobs
- **Job Processing**: Logs job start with affiliate report ID
- **Reconciliation Results**: Logs completion with status
- **Error Handling**: Logs failures with full context
- **Graceful Shutdown**: Handles stop signals properly

### Worker Health Monitoring

**Signs of Healthy Worker**:
- Regular "Processing reconciliation job" messages
- Successful job completions with status
- Proper database session management
- Clean shutdown on application termination

**Signs of Unhealthy Worker**:
- Frequent error messages
- Jobs not being processed
- Database connection issues
- Memory leaks (monitor system resources)

## 9. Troubleshooting Guide
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
