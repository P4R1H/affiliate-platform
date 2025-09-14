# Queue & Worker Subsystem

Describes how asynchronous reconciliation jobs are prioritized, delayed, and executed.

## 1. Goals
| Goal | Mechanism |
|------|-----------|
| Decouple ingestion from reconciliation | Priority + delay queue (Redis-backed or in-memory) |
| Control ordering & urgency | Named priority labels mapping to numeric weights |
| Support scheduled retries | Delay parameter / scheduled heap (or Redis sorted set) |
| Avoid starvation | Two-queue strategy separating ready vs future jobs |
| Simplicity (MVP) | Single thread worker |
| Restart resilience | Redis-backed persistence with in-memory fallback |

## 2. Data Structures

### In-Memory Queue
```
_ready_heap: [(priority_value, seq, QueueItem)]
_scheduled_heap: [(ready_at_ts, priority_value, seq, QueueItem)]
```

### Redis Queue
```
Redis List: affiliate:ready_queue - stores serialized ready jobs
Redis Sorted Set: affiliate:scheduled_jobs - scores=ready_at_ts, members=serialized jobs
```

Sequence number (`seq`) provides FIFO ordering within same priority & timestamp.

Threading: Uses `threading.RLock()` for reentrant locking and `threading.Condition()` for efficient waiting/notification. The condition variable enables blocking dequeue to wait for new items or scheduled items becoming ready without busy polling.

## 2.1 Queue Initialization & Fallback Mechanism

The system automatically selects the appropriate queue implementation based on configuration and availability:

1. **Configuration Check**: If `QUEUE_SETTINGS.use_redis` is `true`, attempt Redis queue
2. **Dependency Check**: Verify Redis Python package is installed
3. **Connection Test**: Attempt to connect to Redis server and perform health check
4. **Fallback**: If any step fails, use in-memory queue as fallback

### Redis Queue Fallback Behavior
- **Initialization**: Redis queue creates an in-memory fallback queue instance
- **Runtime Health Checks**: Before each operation, Redis connectivity is verified
- **Automatic Switching**: If Redis becomes unavailable during operation, seamlessly switches to in-memory queue
- **Recovery**: When Redis connection is restored, switches back to Redis-backed operations
- **Data Consistency**: Jobs enqueued during Redis downtime are stored in memory and processed normally

### create_queue() Function Logic
```python
def create_queue():
    if QUEUE_SETTINGS.use_redis:
        if redis_package_available:
            redis_queue = RedisQueue()
            if redis_queue.health_check():
                return redis_queue  # Use Redis
            else:
                logger.warning("Redis unavailable, using in-memory")
        else:
            logger.warning("Redis package not installed, using in-memory")
    return PriorityDelayQueue()  # Fallback
```

## 3. Enqueue Path
1. Compute `ready_at = now + delay_seconds`.
2. Assign sequence id.
3. If Redis is active:
   - If `ready_at <= now` push to Redis list; else add to Redis sorted set with score = `ready_at`.
4. Otherwise (in-memory fallback):
   - If `ready_at <= now` push to `_ready_heap`; else to `_scheduled_heap`.

Validation includes:
- Priority existence check.
- Capacity check vs `QUEUE_SETTINGS.max_in_memory`.
- Shutdown guard.

## 4. Dequeue Path
### Redis Queue:
1. Perform Redis health check; fall back to in-memory queue if unavailable
2. Promote all scheduled items in Redis sorted set whose `ready_at <= now` into ready list.
3. Use blocking pop (BLPOP) from ready list.
4. If blocking times out, check Redis health and fall back to in-memory queue if needed.

### In-Memory Queue:
1. Promote all scheduled items whose `ready_at <= now` into ready heap.
2. If ready heap non-empty, pop lowest priority_value (higher logical priority) then earliest seq.
3. If empty and blocking, compute wait time until next scheduled item (or indefinite wait) and condition wait.
4. Exit returning `None` only on timeout or after shutdown + empty.

## 5. Priority Semantics
Lower numeric value = higher priority. Example mapping (configure in `QUEUE_SETTINGS.priorities`):
| Label | Value | Meaning |
|-------|-------|---------|
| high | 0 | Urgent anomalies / manual review tasks (future) |
| normal | 5 | Default reconciliation workload |
| low | 10 | Backfill or degraded data tasks |

Current system enqueues all submissions as `normal`; future suspicion scoring can upgrade priority (e.g., extreme CTR) before enqueue.

## 6. Delay / Scheduling Use Cases
| Use Case | Delay Source |
|----------|--------------|
| Retry missing data | `scheduled_retry_at` (future external scheduler re-enqueue) |
| Throttling low-trust affiliates | Potential dynamic delay injection |
| Backoff after platform rate limit | Could compute adaptive delay |

Presently, the queue itself does not auto-reschedule retries; a scheduler (TBD) would read `scheduled_retry_at`, compute delay, and enqueue accordingly.

## 7. Worker Thread Model
| Aspect | Details |
|--------|---------|
| Threading | Single daemon thread with configurable poll timeout (default 5.0s) |
| Loop | Blocking dequeue with timeout to avoid indefinite waits |
| Error Handling | Exceptions caught at worker layer with structured logging and test-visible exception store |
| Shutdown | Graceful shutdown via stop event; worker exits when queue empty |
| Session Management | Fresh SQLAlchemy session per job with proper cleanup in finally block |

## 8. Circuit Breaker Interaction
Worker invokes reconciliation → `PlatformFetcher` consults `GLOBAL_CIRCUIT_BREAKER` → may preempt network fetch. Breaker is process-local (no cross-instance coordination in MVP). States:
| State | Behavior |
|-------|---------|
| CLOSED | Calls allowed |
| OPEN | Calls denied until `open_cooldown_seconds` elapsed |
| HALF_OPEN | Limited `half_open_probe_count` trial calls |

Failures (including rate limit) increment, success resets.

## 9. Queue Item Structure
`QueueItem(job, priority_label, priority_value, enqueued_at, ready_at, seq)` wraps `ReconciliationJob(affiliate_report_id, priority, scheduled_at, correlation_id)`.
- `job` holds reconciliation payload with affiliate report ID and optional correlation tracking
- `correlation_id` enables request tracing across queue operations
- Extensible to structured command pattern if expansion needed

## 10. Test Utilities
`purge()` clears both queues (added for test isolation). Not used in production runtime.

## 11. Queue Inspection
`queue.snapshot()` returns thread-safe statistics:
```python
{
    "depth": total_queued_jobs,
    "ready": ready_heap_size,
    "scheduled": scheduled_heap_size,
    "shutdown": shutdown_flag,
    "redis_active": True/False  # Redis queue status
}
```
Useful for monitoring queue health and debugging backlogs.

## 12. Worker Exception Tracking
For test visibility, worker exceptions are captured in `LAST_EXCEPTIONS` list:
```python
{
    "report_id": affiliate_report_id,
    "error": str(exception),
    "type": exception_class_name
}
```
This enables test assertions on failure patterns without external logging dependencies.

## 13. Failure Modes
| Failure | Impact | Mitigation | Backlog |
|---------|--------|------------|---------|
| Worker crash mid-reconciliation | Lost attempt & potential trust shift not applied | Single process reduces concurrency risks | Add idempotent attempt table / resume mechanism |
| Silent exception consumed | Stuck pending logs | Logging (ensure error-level) | Dead-letter queue / metrics |
| Unbounded queue growth | Memory pressure | Capacity guard | Backpressure signal to API (429) |
| Starvation by future high priority item | Delayed normal jobs | Two-queue design | n/a |
| Redis connection lost | Jobs in memory only; no data loss | Automatic fallback to in-memory queue | Seamless operation continues |

## 14. Scaling Path
| Stage | Change |
|-------|--------|
| Multi-thread | Add worker pool (ensure DB session per thread) |
| Multi-process | Already supported via Redis queue implementation |
| Distributed breaker | External store (Redis) for breaker shared state |
| Dynamic priority | Inline risk scoring at enqueue time |

## 15. Instrumentation Roadmap
| Metric | Insight |
|--------|---------|
| queue_depth | Backlog pressure |
| dequeue_latency_histogram | Worker responsiveness |
| job_processing_duration | Reconciliation execution time |
| job_failures_total | Reliability tracking |
| breaker_state_gauge{platform} | Integration stability |
| redis_health | Redis connectivity status |

## 16. Security & Abuse Considerations
- Flood of submissions could saturate queue: implement rate limiting per affiliate (future).
- Malicious adapter code injection risk mitigated by controlled adapter modules (no dynamic remote loads).

## 17. Example Timeline (Normal Flow)
```
T+00ms enqueue report #101 (priority=normal)
T+02ms worker dequeues #101
T+120ms reconciliation complete (MATCHED)
T+121ms queue empty → blocking wait
```

## 18. Example Timeline (Delayed Retry)
```
Attempt 1 missing -> scheduled_retry_at = now + 30m (NOT auto-enqueued yet)
External scheduler (future) enqueues job with delay_seconds=remaining
Queue places job in scheduled_heap/sorted set; promotes at ready_at
Worker processes attempt 2
```

## 19. Configuration Reference
| Key | Usage |
|-----|-------|
| QUEUE_SETTINGS.priorities | Mapping label→int priority |
| QUEUE_SETTINGS.max_in_memory | Capacity protection |
| QUEUE_SETTINGS.warn_depth | Logging threshold for backlog |
| QUEUE_SETTINGS.use_redis | Enable Redis queue (boolean) |
| QUEUE_SETTINGS.redis_url | Redis connection string |
| QUEUE_SETTINGS.redis_ready_key | Redis key for ready jobs list |
| QUEUE_SETTINGS.redis_scheduled_key | Redis key for scheduled jobs sorted set |
| QUEUE_SETTINGS.redis_health_check_timeout | Timeout for Redis health checks |

## 20. Redis Deployment Requirements
To use the Redis-backed queue (recommended for production), you need:

1. **Redis Server**
   - Minimum Version: Redis 5.0+
   - Memory: 1GB minimum recommended
   - Persistence: AOF (Append-Only File) recommended for durability

2. **Environment Variables**
   ```
   USE_REDIS_QUEUE=true
   REDIS_URL=redis://hostname:6379/0
   REDIS_HEALTH_CHECK_TIMEOUT=2.0
   ```

3. **Network Configuration**
   - Ensure the application server can connect to Redis on the configured port
   - For WSL testing: `redis://localhost:6379/0`
   - For production: Consider Redis authentication and TLS

4. **Monitoring**
   - Monitor Redis memory usage
   - Set up alerts for Redis connectivity issues
   - Watch queue depth metrics for backlog detection

5. **Dependencies**
   - Python redis package (`pip install redis`)

6. **Fallback Mechanism**
   - In-memory queue automatically used if Redis is unavailable
   - Check logs for Redis connection status
   - Jobs enqueued during Redis downtime are safely stored in memory
   - Automatic recovery when Redis connection is restored

---
