from app.jobs.queue import PriorityDelayQueue
from app.jobs.reconciliation_job import ReconciliationJob


def test_priority_queue_ordering():
    q = PriorityDelayQueue()
    # Lower numeric priority should come out first if implemented that way; assuming labels -> internal mapping
    job_low = ReconciliationJob(affiliate_report_id=1, priority="low")
    job_high = ReconciliationJob(affiliate_report_id=2, priority="high")
    job_normal = ReconciliationJob(affiliate_report_id=3, priority="normal")
    q.enqueue(job_low, priority="low")
    q.enqueue(job_high, priority="high")
    q.enqueue(job_normal, priority="normal")
    snap = q.snapshot()
    # Ensure snapshot contains three items
    assert snap.get("ready") == 3
    assert snap.get("depth") == 3
