"""Observability helpers (correlation IDs, safe logging contexts)."""
from __future__ import annotations
import uuid
from typing import Any, Dict, Mapping

REQUEST_ID_HEADER = "X-Request-ID"

def ensure_request_id(headers: Mapping[str, str]) -> str:
    return headers.get(REQUEST_ID_HEADER, None) or str(uuid.uuid4())

__all__ = ["ensure_request_id", "REQUEST_ID_HEADER"]
