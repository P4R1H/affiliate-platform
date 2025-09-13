from app.utils.backoff import compute_backoff_seconds


def test_backoff_growth_and_cap():
    first = compute_backoff_seconds(1, base=1, factor=2, max_seconds=10, jitter_pct=0.0)
    second = compute_backoff_seconds(2, base=1, factor=2, max_seconds=10, jitter_pct=0.0)
    third = compute_backoff_seconds(3, base=1, factor=2, max_seconds=10, jitter_pct=0.0)
    assert first == 1
    assert second == 2
    assert third == 4
    capped = compute_backoff_seconds(10, base=1, factor=2, max_seconds=5, jitter_pct=0.0)
    assert capped <= 5
