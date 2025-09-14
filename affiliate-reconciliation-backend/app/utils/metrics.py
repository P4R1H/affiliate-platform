"""Pure metric math helpers used by classification & reconciliation."""
from __future__ import annotations

from typing import Optional


def safe_div(numerator: float | int, denominator: float | int) -> float:
    if denominator in (0, 0.0):
        return 0.0
    return float(numerator) / float(denominator)


def pct_diff(affiliate_value: int, platform_value: int) -> Optional[float]:
    """Calculate percentage difference between affiliate and platform values."""
    if platform_value == 0 and affiliate_value == 0:
        return 0.0
    if platform_value == 0:
        return 1.0
    return abs(affiliate_value - platform_value) / float(platform_value)


def apply_growth_allowance(platform_value: int, elapsed_hours: float, growth_per_hour: float, cap_hours: int) -> int:
    """Apply growth allowance to platform value based on elapsed time."""
    hours = min(max(elapsed_hours, 0.0), float(cap_hours))
    allowance_factor = 1 + (growth_per_hour * hours)
    return int(round(platform_value * allowance_factor))


__all__ = ["safe_div", "pct_diff", "apply_growth_allowance"]
