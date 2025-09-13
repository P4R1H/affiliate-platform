"""Background worker for processing reconciliation jobs."""
from __future__ import annotations

import threading
import time
from typing import Callable

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.jobs.queue import PriorityDelayQueue
from app.jobs.reconciliation_job import ReconciliationJob
from app.services.reconciliation_engine import run_reconciliation
from app.utils import get_logger

logger = get_logger(__name__)


class ReconciliationWorker:
    def __init__(self, queue: PriorityDelayQueue, *, poll_timeout: float = 5.0):
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
        finally:
            session.close()


__all__ = ["ReconciliationWorker"]
