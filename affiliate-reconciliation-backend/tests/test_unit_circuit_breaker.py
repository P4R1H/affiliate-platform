from datetime import datetime, timedelta, timezone
from app.utils.circuit_breaker import CircuitBreaker


def test_circuit_opens_and_half_open_cycle():
    cb = CircuitBreaker()
    platform = "platformX"
    # Trigger failures
    # Failure threshold from config is 5; exceed it
    for _ in range(6):
        cb.record_failure(platform)
    allowed, reason = cb.allow_call(platform)
    assert allowed is False and reason == "circuit_open"
    st = cb._states[platform]
    assert st.state == "OPEN"
    assert st.opened_at is not None
