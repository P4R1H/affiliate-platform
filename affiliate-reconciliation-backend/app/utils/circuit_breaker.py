"""In-memory circuit breaker for platform integrations (process-local)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict

from app.config import CIRCUIT_BREAKER


@dataclass
class BreakerState:
    failures: int = 0
    state: str = "CLOSED"
    opened_at: datetime | None = None
    half_open_probes: int = 0


class CircuitBreaker:
    def __init__(self):
        self._states: Dict[str, BreakerState] = {}

    def _get(self, platform: str) -> BreakerState:
        return self._states.setdefault(platform, BreakerState())

    def allow_call(self, platform: str) -> tuple[bool, str | None]:
        st = self._get(platform)
        if st.state == "CLOSED":
            return True, None
        if st.state == "OPEN":
            cooldown = CIRCUIT_BREAKER["open_cooldown_seconds"]  # type: ignore[index]
            if st.opened_at and datetime.now(timezone.utc) - st.opened_at >= timedelta(seconds=cooldown):
                st.state = "HALF_OPEN"
                st.half_open_probes = 0
            else:
                return False, "circuit_open"
        if st.state == "HALF_OPEN":
            probe_limit = CIRCUIT_BREAKER["half_open_probe_count"]  # type: ignore[index]
            if st.half_open_probes >= probe_limit:  # type: ignore[arg-type]
                return False, "half_open_probe_exhausted"
            st.half_open_probes += 1
            return True, None
        return True, None

    def record_success(self, platform: str) -> None:
        st = self._get(platform)
        st.failures = 0
        if st.state in {"OPEN", "HALF_OPEN"}:
            st.state = "CLOSED"
            st.opened_at = None
            st.half_open_probes = 0

    def record_failure(self, platform: str) -> None:
        st = self._get(platform)
        st.failures += 1
        threshold = CIRCUIT_BREAKER["failure_threshold"]  # type: ignore[index]
        if st.state == "CLOSED" and st.failures >= threshold:  # type: ignore[arg-type]
            st.state = "OPEN"
            st.opened_at = datetime.now(timezone.utc)
        elif st.state == "HALF_OPEN":
            st.state = "OPEN"
            st.opened_at = datetime.now(timezone.utc)

    def snapshot(self) -> dict[str, dict[str, object]]:
        return {
            k: {
                "failures": v.failures,
                "state": v.state,
                "opened_at": v.opened_at.isoformat() if v.opened_at else None,
                "half_open_probes": v.half_open_probes,
            }
            for k, v in self._states.items()
        }


GLOBAL_CIRCUIT_BREAKER = CircuitBreaker()

__all__ = ["CircuitBreaker", "GLOBAL_CIRCUIT_BREAKER"]
