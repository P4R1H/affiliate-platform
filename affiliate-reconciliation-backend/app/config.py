"""Core application configuration & tunable governance rules.

All business rules that may evolve (tolerances, growth allowances, trust deltas,
retry/circuit thresholds, queue priorities, alerting) are centralized here so
they can be adjusted without diving into service logic. Real deployments would
likely override via environment variables or a dynamic configuration service;
for this MVP we keep them as module constants (mutable dicts allowed if tests
monkeypatch values).
"""
from __future__ import annotations

import os
from typing import Final

_seed_env = os.getenv("INTEGRATIONS_RANDOM_SEED")
INTEGRATIONS_RANDOM_SEED: int | None = int(_seed_env) if _seed_env and _seed_env.strip() else None

# Shared across mock integrations (probability of simulated failure)
MOCK_FAILURE_RATE: float = float(os.getenv("MOCK_FAILURE_RATE", "0.05"))

# Network timeout for the ONLY real outbound call (Reddit link resolution)
REDDIT_LINK_RESOLVE_TIMEOUT: float = float(os.getenv("REDDIT_LINK_RESOLVE_TIMEOUT", "10"))

# ----------------------------- Reconciliation ----------------------------- #
RECONCILIATION_SETTINGS: dict[str, float | dict[str, float]] = {
	# Base tolerance BEFORE growth allowance. Diff within this is a match.
	"base_tolerance_pct": 0.05,  # 5%
	# Discrepancy tier thresholds (upper bounds). > medium_max => HIGH.
	"discrepancy_tiers": {
		"low_max": 0.10,     # 10%
		"medium_max": 0.20,  # 20%
	},
	# Overclaim threshold: affiliate significantly above platform.
	"overclaim_threshold_pct": 0.20,   # 20%
	"overclaim_critical_pct": 0.50,    # 50% triggers CRITICAL alert
	# Allowance for organic growth between submission & fetch.
	"growth_per_hour_pct": 0.10,       # 10% per hour
	"growth_cap_hours": 24,            # Cap growth adjustment window
}

# ------------------------------ Trust Scoring ----------------------------- #
# Trust score is maintained in [0,1] range for MVP (float). Deltas reference
# additive adjustments that will later be clamped.
TRUST_SCORING: dict[str, float | dict[str, float]] = {
	"min_score": 0.0,
	"max_score": 1.0,
	# Event → delta (positive or negative). These are *not* percentages, just
	# additive adjustments; tune conservatively to avoid volatility.
	"events": {
		"perfect_match": +0.01,
		"minor_discrepancy": -0.01,
		"medium_discrepancy": -0.03,
		"high_discrepancy": -0.05,
		"overclaim": -0.10,
		"impossible_submission": -0.15,
	},
	# Thresholds for operational behaviors (future use / prioritisation)
	"reduced_frequency_threshold": 0.75,
	"increased_monitoring_threshold": 0.50,
	"manual_review_threshold": 0.25,
}

# ----------------------------- Circuit Breaker ---------------------------- #
CIRCUIT_BREAKER: dict[str, int | float] = {
	"failure_threshold": 5,          # Consecutive failures before OPEN
	"open_cooldown_seconds": 300,    # Stay OPEN for 5 minutes
	"half_open_probe_count": 3,      # Probes allowed in HALF_OPEN
}

# --------------------------------- Backoff -------------------------------- #
BACKOFF_POLICY: dict[str, int | float] = {
	"base_seconds": 1,
	"factor": 2,          # Exponential factor
	"max_seconds": 60,
	"max_attempts": 3,
	"jitter_pct": 0.10,   # +/-10% jitter
}

# ------------------------------- Retry Policy ----------------------------- #
RETRY_POLICY: dict[str, dict[str, int | float]] = {
	# Missing platform data (timeouts, rate limiting) scenario
	"missing_platform_data": {
		"initial_delay_minutes": 30,
		"max_attempts": 5,
		"window_hours": 24,
	},
	# Partial data (optional second fetch attempt)
	"incomplete_platform_data": {
		"max_additional_attempts": 1,
	},
}

# --------------------------------- Queue ---------------------------------- #
QUEUE_SETTINGS: dict[str, dict[str, int] | int] = {
	"priorities": {  # Lower number = higher priority
		"high": 0,
		"normal": 5,
		"low": 10,
	},
	"warn_depth": 1000,
	"max_in_memory": 5000,
}

# -------------------------------- Alerting -------------------------------- #
ALERTING_SETTINGS: dict[str, float | int] = {
	"platform_down_escalation_minutes": 120,
	"repeat_overclaim_window_hours": 6,  # Consecutive high discrepancies escalate
}

# --------------------------- Data Quality Rules --------------------------- #
DATA_QUALITY_SETTINGS: dict[str, float | int] = {
	# Ratio thresholds
	"max_ctr_pct": 0.35,              # clicks/views > 35% suspicious
	"max_cvr_pct": 0.60,              # conversions/clicks > 60% suspicious
	# Growth / spike detection
	"max_views_growth_pct": 5.0,      # >500% vs previous report views
	"max_clicks_growth_pct": 5.0,
	"max_conversions_growth_pct": 5.0,
	# Evidence requirement thresholds
	"evidence_required_views": 50000, # If claimed views exceed & no evidence flag
	# Non-monotonic allowances (allow small negative noise)
	"monotonic_tolerance": 0.01,      # 1% tolerance for small decreases
	# Minimum baseline to evaluate certain ratios
	"min_views_for_ctr": 100,
	"min_clicks_for_cvr": 20,
}

if INTEGRATIONS_RANDOM_SEED is not None:
	import random
	random.seed(INTEGRATIONS_RANDOM_SEED)

__all__ = [
	"INTEGRATIONS_RANDOM_SEED",
	"MOCK_FAILURE_RATE",
	"REDDIT_LINK_RESOLVE_TIMEOUT",
	# Rule groups
	"RECONCILIATION_SETTINGS",
	"TRUST_SCORING",
	"CIRCUIT_BREAKER",
	"BACKOFF_POLICY",
	"RETRY_POLICY",
	"QUEUE_SETTINGS",
	"ALERTING_SETTINGS",
	"DATA_QUALITY_SETTINGS",
    # Discord / external interface
    "DISCORD_BOT_TOKEN",
    "DISCORD_COMMAND_GUILDS",
    "ENABLE_DISCORD_BOT",
    "API_BASE_URL",
	"BOT_INTERNAL_TOKEN",
]

# ------------------------------- Discord Bot ------------------------------ #
# Optional Discord bot integration. If ENABLE_DISCORD_BOT is true and a token
# is provided, the service/discord_bot.py module can be launched separately to
# expose slash commands as an alternative affiliate submission interface.
ENABLE_DISCORD_BOT: bool = False
DISCORD_BOT_TOKEN: str | None = os.getenv("DISCORD_BOT_TOKEN") or None

# Comma-separated guild IDs for faster command registration during development.
# Leave empty to register globally (may take up to 1 hour to propagate).
_guilds_raw = os.getenv("DISCORD_COMMAND_GUILDS", "").strip()
DISCORD_COMMAND_GUILDS: list[int] = [int(g.strip()) for g in _guilds_raw.split(",") if g.strip().isdigit()]

# Base URL for the FastAPI service the bot will call. Default local dev address.
API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")

# Single internal token used by the Discord bot for privileged but narrowly
# scoped submission endpoints (alternate to affiliate API keys). Keep this
# secret secure and rotate periodically.
BOT_INTERNAL_TOKEN: str | None = os.getenv("BOT_INTERNAL_TOKEN") or None

