"""Platform fetch wrapper applying circuit breaker, retries, and partial data tagging.

This module abstracts the act of retrieving authoritative metrics for a post
from the associated platform integration adapter. Real adapters live in
`app.integrations.<platform>` modules and expose a `fetch_post_metrics(post)`
or similar function. For this MVP we assume integrations return a dict with
keys: views, clicks, conversions (some may be missing / None for partial data).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple
from datetime import datetime, timezone

from app.utils.circuit_breaker import GLOBAL_CIRCUIT_BREAKER
from app.utils.backoff import compute_backoff_seconds
from app.config import BACKOFF_POLICY
from app.utils import get_logger

logger = get_logger(__name__)


@dataclass
class FetchOutcome:
    success: bool
    platform_metrics: dict[str, int | None] | None
    partial_missing: list[str]
    attempts: int
    error_code: str | None = None
    error_message: str | None = None
    rate_limited: bool = False


class PlatformFetcher:
    """Encapsulates resilient fetch logic for a single reconciliation attempt."""

    def __init__(self, max_attempts: int | None = None):
        self.max_attempts = int(max_attempts or BACKOFF_POLICY["max_attempts"])  # type: ignore[index]

    def _call_adapter(self, platform_name: str, post_url: str) -> Tuple[dict[str, Any] | None, str | None, str | None]:  # noqa: D401
        """Invoke the platform adapter. Returns (data, error_code, error_message)."""
        try:
            # Dynamically import adapter module based on platform_name (lowercase)
            module_name = f"app.integrations.{platform_name.lower()}"
            module = __import__(module_name, fromlist=["fetch_post_metrics"])
            if not hasattr(module, "fetch_post_metrics"):
                return None, "adapter_missing", f"Adapter missing fetch_post_metrics for {platform_name}"
            data = module.fetch_post_metrics(post_url)  # type: ignore[attr-defined]
            if not isinstance(data, dict):
                return None, "invalid_adapter_return", "Adapter did not return dict"
            return data, None, None
        except Exception as e:  # broad by design to classify failures
            msg = str(e)
            # Basic classification
            if "rate limit" in msg.lower():
                return None, "rate_limited", msg
            if "auth" in msg.lower() or "401" in msg or "403" in msg:
                return None, "auth_error", msg
            return None, "fetch_error", msg

    def fetch(self, platform_name: str, post_url: str) -> FetchOutcome:
        """Fetch metrics with circuit breaker + retry semantics.

        Circuit breaker denial returns immediate MISSING scenario (caller will
        schedule retry). Rate limiting returns a rate_limited outcome so caller
        can differentiate neutral retries.
        """
        allow, reason = GLOBAL_CIRCUIT_BREAKER.allow_call(platform_name)
        if not allow:
            logger.warning(
                "Platform fetch skipped due to circuit breaker",
                platform=platform_name,
                reason=reason,
            )
            return FetchOutcome(
                success=False,
                platform_metrics=None,
                partial_missing=["views", "clicks", "conversions"],
                attempts=0,
                error_code=reason,
                error_message=f"Circuit breaker denies call: {reason}",
            )

        attempts = 0
        last_error_code: str | None = None
        last_error_message: str | None = None
        rate_limited = False

        while attempts < self.max_attempts:
            attempts += 1
            data, err_code, err_msg = self._call_adapter(platform_name, post_url)
            if err_code is None and data is not None:
                # Success
                GLOBAL_CIRCUIT_BREAKER.record_success(platform_name)
                missing = [k for k in ("views", "clicks", "conversions") if k not in data or data.get(k) is None]
                metrics: dict[str, int | None] = {
                    "views": data.get("views"),
                    "clicks": data.get("clicks"),
                    "conversions": data.get("conversions"),
                }
                return FetchOutcome(
                    success=True,
                    platform_metrics=metrics,
                    partial_missing=missing,
                    attempts=attempts,
                )

            # Failure path
            last_error_code = err_code
            last_error_message = err_msg
            if err_code == "rate_limited":
                rate_limited = True
            if err_code == "auth_error":
                GLOBAL_CIRCUIT_BREAKER.record_failure(platform_name)
                # Auth errors are terminal – do not retry more
                break
            # Record failure and maybe retry
            GLOBAL_CIRCUIT_BREAKER.record_failure(platform_name)
            if attempts >= self.max_attempts:
                break
            backoff = compute_backoff_seconds(attempts)
            logger.warning(
                "Platform fetch retry scheduled",
                platform=platform_name,
                attempt=attempts,
                backoff_seconds=round(backoff, 2),
                error_code=err_code,
            )
            # Lightweight sleep for synchronous context (could be async sleep if needed)
            import time as _time
            _time.sleep(backoff)

        return FetchOutcome(
            success=False,
            platform_metrics=None,
            partial_missing=["views", "clicks", "conversions"],
            attempts=attempts,
            error_code=last_error_code,
            error_message=last_error_message,
            rate_limited=rate_limited,
        )


__all__ = ["PlatformFetcher", "FetchOutcome"]
