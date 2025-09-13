from app.services.trust_scoring import apply_trust_event, bucket_for_priority
from app.models.db.enums import TrustEvent


def test_apply_trust_event_bounds():
    # Large positive adjustments should clamp at 1.0
    score = 0.95
    new, delta = apply_trust_event(score, TrustEvent.PERFECT_MATCH)
    assert 0 <= new <= 1
    assert abs((new - score) - delta) < 1e-9


def test_bucket_for_priority():
    assert bucket_for_priority(0.99) == "high_trust"
    mid = bucket_for_priority(0.6)
    assert mid in {"normal", "low_trust"}
    assert bucket_for_priority(0.1) in {"critical", "low_trust"}
