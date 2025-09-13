from app.services.discrepancy_classifier import classify
from app.models.db.enums import ReconciliationStatus, TrustEvent


def test_classify_matched():
    # Identical claimed vs platform values -> MATCHED
    result = classify(100, 10, 1, 100, 10, 1, elapsed_hours=0.0)
    assert result.status == ReconciliationStatus.MATCHED
    assert result.trust_event == TrustEvent.PERFECT_MATCH
    assert result.views_discrepancy == 0
    assert result.max_discrepancy_pct in (0.0, None)


def test_classify_low_medium_high_progression():
    r_low = classify(110, 10, 1, 100, 10, 1, elapsed_hours=1.0)  # ~10% discrepancy views
    assert r_low.status in {ReconciliationStatus.DISCREPANCY_LOW, ReconciliationStatus.DISCREPANCY_MEDIUM}
    r_med = classify(150, 10, 1, 100, 10, 1, elapsed_hours=1.0)
    r_high = classify(250, 10, 1, 100, 10, 1, elapsed_hours=1.0)
    assert (r_high.max_discrepancy_pct or 0) >= (r_med.max_discrepancy_pct or 0)


def test_classify_overclaim():
    r = classify(1000, 200, 50, 100, 200, 50, elapsed_hours=0.5)
    assert r.status in {ReconciliationStatus.AFFILIATE_OVERCLAIMED, ReconciliationStatus.DISCREPANCY_HIGH}
    assert r.views_discrepancy > 0
    # Overclaim should yield an OVERCLAIM or high discrepancy related trust event
    assert r.trust_event in {TrustEvent.OVERCLAIM, TrustEvent.HIGH_DISCREPANCY}
