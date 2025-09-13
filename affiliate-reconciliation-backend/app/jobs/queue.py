"""In-memory priority + delay queue (single-process MVP).

Features:
- Priority ordering (lower numeric priority value = higher priority).
- Optional delay (scheduled execution time) per job.
- Capacity limits / backpressure via QUEUE_SETTINGS.
- Thread-safe with condition variable.

Two-heaps strategy:
 1. ready_heap: (priority, seq, job)
 2. scheduled_heap: (ready_at_ts, priority, seq, job)

On enqueue:
  - If ready_at <= now -> push to ready_heap else scheduled_heap.
On dequeue:
  - Promote any scheduled items whose ready_at <= now.
  - Pop highest priority from ready_heap (ties resolved by seq FIFO).
  - If nothing ready: wait until next scheduled item's ready_at or until notified.

This avoids starvation of currently-ready lower-priority items caused by a far-future
higher-priority entry which would happen with a single composite heap keyed by (ready_at, priority).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Iterable, Callable
import threading
import time
import heapq
from datetime import datetime, timezone

from app.config import QUEUE_SETTINGS
from app.utils import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class QueueItem:
    job: Any
    priority_label: str
    priority_value: int
    enqueued_at: float
    ready_at: float
    seq: int


class PriorityDelayQueue:
    def __init__(self) -> None:
        priorities_cfg = QUEUE_SETTINGS.get("priorities", {})  # type: ignore[assignment]
        self._priority_map: dict[str, int] = priorities_cfg if isinstance(priorities_cfg, dict) else {"normal": 5}
        self._warn_depth = int(QUEUE_SETTINGS.get("warn_depth", 1000))  # type: ignore[arg-type]
        self._max_in_memory = int(QUEUE_SETTINGS.get("max_in_memory", 5000))  # type: ignore[arg-type]
        self._lock = threading.RLock()
        self._cv = threading.Condition(self._lock)
        self._ready_heap: list[tuple[int, int, QueueItem]] = []  # (priority_value, seq, item)
        self._scheduled_heap: list[tuple[float, int, int, QueueItem]] = []  # (ready_at_ts, priority_value, seq, item)
        self._seq_counter = 0
        self._shutdown = False

    # ----------------------------- internal helpers ----------------------------- #
    def _next_seq(self) -> int:
        self._seq_counter += 1
        return self._seq_counter

    def _promote_scheduled(self) -> None:
        now_ts = time.time()
        while self._scheduled_heap and self._scheduled_heap[0][0] <= now_ts:
            ready_at_ts, priority_value, seq, item = heapq.heappop(self._scheduled_heap)
            heapq.heappush(self._ready_heap, (priority_value, seq, item))

    def _await_next_ready(self, timeout: Optional[float]) -> bool:
        """Wait until something becomes ready or timeout expires.
        Returns True if we should re-check, False if timeout triggered with no items.
        """
        if self._ready_heap:
            return True
        # Determine next wake-up time
        if not self._scheduled_heap:
            if timeout is None:
                self._cv.wait()
                return True
            else:
                self._cv.wait(timeout=timeout)
                return True
        next_ready_ts = self._scheduled_heap[0][0]
        now_ts = time.time()
        wait_time = max(0.0, next_ready_ts - now_ts)
        if timeout is not None:
            wait_time = min(wait_time, timeout)
        if wait_time > 0:
            self._cv.wait(timeout=wait_time)
        return True

    # ----------------------------- public API ----------------------------- #
    def enqueue(self, job: Any, *, priority: str = "normal", delay_seconds: float = 0.0) -> QueueItem:
        with self._lock:
            if self._shutdown:
                raise RuntimeError("Queue shutdown")
            if len(self) >= self._max_in_memory:
                raise OverflowError("Queue capacity exceeded")
            if priority not in self._priority_map:
                raise ValueError(f"Unknown priority '{priority}'")
            now_ts = time.time()
            ready_at_ts = now_ts + max(0.0, delay_seconds)
            seq = self._next_seq()
            item = QueueItem(
                job=job,
                priority_label=priority,
                priority_value=self._priority_map[priority],
                enqueued_at=now_ts,
                ready_at=ready_at_ts,
                seq=seq,
            )
            if ready_at_ts <= now_ts:
                heapq.heappush(self._ready_heap, (item.priority_value, item.seq, item))
            else:
                heapq.heappush(self._scheduled_heap, (ready_at_ts, item.priority_value, item.seq, item))
            if self.depth() >= self._warn_depth:
                logger.warning("Queue depth warning", depth=self.depth())
            self._cv.notify()
            return item

    def dequeue(self, *, block: bool = True, timeout: Optional[float] = None) -> Any:
        """Pop next ready job. Returns None if non-blocking and empty or timeout occurs."""
        end_time = None if timeout is None else time.time() + timeout
        with self._lock:
            while True:
                if self._shutdown and not self._ready_heap and not self._scheduled_heap:
                    return None
                # Promote any scheduled items now ready
                self._promote_scheduled()
                if self._ready_heap:
                    _, _, item = heapq.heappop(self._ready_heap)
                    return item.job
                if not block:
                    return None
                # Compute remaining timeout
                remaining = None if end_time is None else max(0.0, end_time - time.time())
                if end_time is not None and remaining == 0:
                    return None
                self._await_next_ready(remaining)

    def shutdown(self) -> None:
        with self._lock:
            self._shutdown = True
            self._cv.notify_all()

    # ----------------------------- test utilities ----------------------------- #
    def purge(self) -> None:
        """Remove all queued (ready + scheduled) jobs.

        Intended for test isolation only; not used in production runtime.
        Safe under lock; any worker currently processing a job continues unaffected.
        """
        with self._lock:
            self._ready_heap.clear()
            self._scheduled_heap.clear()
            self._cv.notify_all()

    # ----------------------------- inspection ----------------------------- #
    def depth(self) -> int:
        return len(self._ready_heap) + len(self._scheduled_heap)

    def __len__(self) -> int:  # pragma: no cover
        return self.depth()

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "depth": self.depth(),
                "ready": len(self._ready_heap),
                "scheduled": len(self._scheduled_heap),
                "shutdown": self._shutdown,
            }


__all__ = ["PriorityDelayQueue", "QueueItem"]
