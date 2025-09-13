"""Core application configuration.

Intentionally minimal: only cross-cutting or environment-driven values.
Platform mock tuning stays local to each integration module to avoid bloat.
"""
from __future__ import annotations

import os

_seed_env = os.getenv("INTEGRATIONS_RANDOM_SEED")
INTEGRATIONS_RANDOM_SEED: int | None = int(_seed_env) if _seed_env and _seed_env.strip() else None

# Shared across mock integrations (probability of simulated failure)
MOCK_FAILURE_RATE: float = float(os.getenv("MOCK_FAILURE_RATE", "0.05"))

# Network timeout for the ONLY real outbound call (Reddit link resolution)
REDDIT_LINK_RESOLVE_TIMEOUT: float = float(os.getenv("REDDIT_LINK_RESOLVE_TIMEOUT", "10"))

if INTEGRATIONS_RANDOM_SEED is not None:
	import random
	random.seed(INTEGRATIONS_RANDOM_SEED)

__all__ = ["INTEGRATIONS_RANDOM_SEED", "MOCK_FAILURE_RATE", "REDDIT_LINK_RESOLVE_TIMEOUT"]
