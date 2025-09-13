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
| high | 1 | Urgent anomalies / manual review tasks (future) |
| normal | 5 | Default reconciliation workload |
| low | 9 | Backfill or degraded data tasks |

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
| Threading | Single daemon thread started in test + app lifespan substitute |
| Loop | Blocking dequeue (no busy wait) |
| Error Handling | Exceptions inside reconciliation should be caught at worker layer (TODO: persistent logging + future DLQ) |
| Shutdown | `queue.shutdown()` sets flag & notifies condition; worker exits when heaps empty |

## 8. Circuit Breaker Interaction
Worker invokes reconciliation → `PlatformFetcher` consults `GLOBAL_CIRCUIT_BREAKER` → may preempt network fetch. Breaker is process-local (no cross-instance coordination in MVP). States:
| State | Behavior |
|-------|---------|
| CLOSED | Calls allowed |
| OPEN | Calls denied until `open_cooldown_seconds` elapsed |
| HALF_OPEN | Limited `half_open_probe_count` trial calls |

Failures (including rate limit) increment, success resets.

## 9. Queue Item Structure
`QueueItem(job, priority_label, priority_value, enqueued_at, ready_at, seq)`.
- `job` currently holds minimal data (affiliate_report_id) via reconciliation job wrapper.
- Extensible to structured command pattern if expansion needed.

## 10. Test Utilities
`purge()` clears both heaps (added for test isolation). Not used in production runtime.

## 11. Failure Modes & Mitigations
| Failure | Impact | Mitigation | Backlog |
|---------|--------|------------|---------|
| Worker crash mid-reconciliation | Lost attempt & potential trust shift not applied | Single process reduces concurrency risks | Add idempotent attempt table / resume mechanism |
| Silent exception consumed | Stuck pending logs | Logging (ensure error-level) | Dead-letter queue / metrics |
| Unbounded queue growth | Memory pressure | Capacity guard | Backpressure signal to API (429) |
| Starvation by future high priority item | Delayed normal jobs | Two-heap design | n/a |

## 12. Scaling Path
| Stage | Change |
|-------|--------|
| Multi-thread | Add worker pool (ensure DB session per thread) |
| Multi-process | Replace with Redis / SQS; adapt enqueue/dequeue interface |
| Distributed breaker | External store (Redis) for breaker shared state |
| Dynamic priority | Inline risk scoring at enqueue time |

## 13. Instrumentation Roadmap
| Metric | Insight |
|--------|---------|
| queue_depth | Backlog pressure |
| dequeue_latency_histogram | Worker responsiveness |
| job_processing_duration | Reconciliation execution time |
| job_failures_total | Reliability tracking |
| breaker_state_gauge{platform} | Integration stability |

## 14. Security & Abuse Considerations
- Flood of submissions could saturate queue: implement rate limiting per affiliate (future).
- Malicious adapter code injection risk mitigated by controlled adapter modules (no dynamic remote loads).

## 15. Example Timeline (Normal Flow)
```
T+00ms enqueue report #101 (priority=normal)
T+02ms worker dequeues #101
T+120ms reconciliation complete (MATCHED)
T+121ms queue empty → blocking wait
```

## 16. Example Timeline (Delayed Retry)
```
Attempt 1 missing -> scheduled_retry_at = now + 30m (NOT auto-enqueued yet)
External scheduler (future) enqueues job with delay_seconds=remaining
Queue places job in scheduled_heap; promotes at ready_at
Worker processes attempt 2
```

## 17. Configuration Reference
| Key | Usage |
|-----|-------|
| QUEUE_SETTINGS.priorities | Mapping label→int priority |
| QUEUE_SETTINGS.max_in_memory | Capacity protection |
| QUEUE_SETTINGS.warn_depth | Logging threshold for backlog |

---
Next: `TESTING_STRATEGY.md`.
