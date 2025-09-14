# Queue & Worker Subsystem

Describes how asynchronous reconciliation jobs are prioritized, delayed, and executed.

## 1. Goals
| Goal | Mechanism |
|------|-----------|
| Decouple ingestion from reconciliation | In-memory priority + delay queue |
| Control ordering & urgency | Named priority labels mapping to numeric weights |
| Support scheduled retries | Delay parameter / scheduled heap |
| Avoid starvation | Two-heap strategy separating ready vs future jobs |
| Simplicity (MVP) | Single thread worker, process-local state |

## 2. Data Structures
```
_ready_heap: [(priority_value, seq, QueueItem)]
_scheduled_heap: [(ready_at_ts, priority_value, seq, QueueItem)]
```
Sequence number (`seq`) provides FIFO ordering within same priority & timestamp.

Threading: Uses `threading.RLock()` for reentrant locking and `threading.Condition()` for efficient waiting/notification. The condition variable enables blocking dequeue to wait for new items or scheduled items becoming ready without busy polling.

## 3. Enqueue Path
1. Compute `ready_at = now + delay_seconds`.
2. Assign sequence id.
3. If `ready_at <= now` push to `_ready_heap`; else to `_scheduled_heap`.
4. Notify condition variable.

Validation includes:
- Priority existence check.
- Capacity check vs `QUEUE_SETTINGS.max_in_memory`.
- Shutdown guard.

## 4. Dequeue Path
Loop:
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
`purge()` clears both heaps (added for test isolation). Not used in production runtime.

## 11. Queue Inspection
`queue.snapshot()` returns thread-safe statistics:
```python
{
    "depth": total_queued_jobs,
    "ready": ready_heap_size,
    "scheduled": scheduled_heap_size,
    "shutdown": shutdown_flag
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
| Failure | Impact | Mitigation | Backlog |
|---------|--------|------------|---------|
| Worker crash mid-reconciliation | Lost attempt & potential trust shift not applied | Single process reduces concurrency risks | Add idempotent attempt table / resume mechanism |
| Silent exception consumed | Stuck pending logs | Logging (ensure error-level) | Dead-letter queue / metrics |
| Unbounded queue growth | Memory pressure | Capacity guard | Backpressure signal to API (429) |
| Starvation by future high priority item | Delayed normal jobs | Two-heap design | n/a |

## 14. Scaling Path
| Stage | Change |
|-------|--------|
| Multi-thread | Add worker pool (ensure DB session per thread) |
| Multi-process | Replace with Redis / SQS; adapt enqueue/dequeue interface |
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
Queue places job in scheduled_heap; promotes at ready_at
Worker processes attempt 2
```

## 19. Configuration Reference
| Key | Usage |
|-----|-------|
| QUEUE_SETTINGS.priorities | Mapping label→int priority |
| QUEUE_SETTINGS.max_in_memory | Capacity protection |
| QUEUE_SETTINGS.warn_depth | Logging threshold for backlog |

---
Next: `TESTING_STRATEGY.md`.
