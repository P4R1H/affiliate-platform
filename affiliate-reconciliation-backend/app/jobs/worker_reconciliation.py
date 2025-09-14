"""Background worker for processing reconciliation jobs."""
from __future__ import annotations

import threading
import time
from typing import Union, Protocol, Any, Optional

from sqlalchemy.orm import Session

from app.config import QUEUE_SETTINGS
from app.database import SessionLocal
from app.jobs.queue import PriorityDelayQueue
from app.jobs.reconciliation_job import ReconciliationJob
from app.services.reconciliation_engine import run_reconciliation
from app.utils import get_logger

# Use optional import for Redis queue to maintain compatibility
try:
    from app.jobs.redis_queue import RedisQueue
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = get_logger(__name__)

# Debug instrumentation store (test visibility)
LAST_EXCEPTIONS: list[dict] = []


# Define a Protocol for queues to make type checking happy
class QueueProtocol(Protocol):
    def enqueue(self, job: Any, *, priority: str = "normal", delay_seconds: float = 0.0) -> Any: ...
    def dequeue(self, *, block: bool = True, timeout: Optional[float] = None) -> Any: ...
    def shutdown(self) -> None: ...
    def snapshot(self) -> dict: ...


class ReconciliationWorker:
    def __init__(self, queue: Union[PriorityDelayQueue, "RedisQueue"], *, poll_timeout: float = 5.0):
        self.queue = queue
        self.poll_timeout = poll_timeout
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():  # pragma: no cover
            return
        self._thread = threading.Thread(target=self._loop, name="reconciliation-worker", daemon=True)
        self._thread.start()
        logger.info("Reconciliation worker started")

    def stop(self) -> None:
        self._stop_event.set()
        logger.info("Reconciliation worker stop requested")

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                job = self.queue.dequeue(timeout=self.poll_timeout)
                if job is None:
                    continue
                if not isinstance(job, ReconciliationJob):
                    logger.warning("Skipping unknown job type", job_type=type(job).__name__)
                    continue
                self._process(job)
            except Exception as e:  # pragma: no cover - defensive
                logger.error("Worker loop error", error=str(e), exc_info=True)
                time.sleep(1)

    def _process(self, job: ReconciliationJob) -> None:
        logger.info("Processing reconciliation job", report_id=job.affiliate_report_id)
        session: Session = SessionLocal()
        try:
            result = run_reconciliation(session, job.affiliate_report_id)
            logger.info("Reconciliation completed", report_id=job.affiliate_report_id, status=result.get("status"))
        except Exception as e:
            logger.error("Reconciliation job failed", report_id=job.affiliate_report_id, error=str(e), exc_info=True)
            try:  # store structured diagnostic for tests
                LAST_EXCEPTIONS.append({
                    "report_id": job.affiliate_report_id,
                    "error": str(e),
                    "type": type(e).__name__,
                })
            except Exception:  # pragma: no cover - defensive
                pass
        finally:
            session.close()


def create_queue() -> Union[PriorityDelayQueue, "RedisQueue"]:
    """Create and return the appropriate queue based on configuration."""
    use_redis = QUEUE_SETTINGS.get("use_redis", False)  # type: ignore[assignment]
    
    if use_redis:
        if not REDIS_AVAILABLE:
            print("REDIS NOT AVAILABLE: Redis package is not installed. Using in-memory queue.")
            logger.warning("REDIS NOT AVAILABLE: Redis package is not installed. Using in-memory queue.")
        else:
            try:
                from app.jobs.redis_queue import RedisQueue
                redis_queue = RedisQueue()
                # Test Redis connection
                if redis_queue.health_check():
                    logger.info("Using Redis-backed queue")
                    print("REDIS CONNECTED: Using Redis-backed queue for job persistence")
                    return redis_queue
                else:
                    print("REDIS CONNECTION FAILED: Redis server is not reachable. Using in-memory queue.")
                    logger.warning("REDIS CONNECTION FAILED: Redis server is not reachable. Using in-memory queue.")
            except Exception as e:
                print(f"REDIS ERROR: {str(e)}. Using in-memory queue.")
                logger.warning(f"Error initializing Redis queue, falling back to in-memory queue", error=str(e))
    
    logger.info("Using in-memory queue")
    return PriorityDelayQueue()


__all__ = ["ReconciliationWorker", "LAST_EXCEPTIONS", "create_queue"]
