"""Discord bot interface for affiliate submissions (Bot-token auth model).

Provides slash commands that proxy to the FastAPI backend so affiliates can
submit and update post metrics directly from Discord.

Key design points:
 - Authorization: Uses a dedicated internal bot token (``BOT_INTERNAL_TOKEN``)
	 sent as ``Authorization: Bot <token>`` plus an ``X-Discord-User-ID`` header.
	 Backend dependency `get_submission_affiliate` validates the bot token and
	 resolves the affiliate via `affiliates.discord_user_id`.
 - Principle of Least Privilege: Bot never reads or uses affiliate API keys.
 - Endpoints proxied:
		 POST /api/v1/submissions/
		 PUT  /api/v1/submissions/{post_id}/metrics
 - Evidence: Optional JSON blob (fallback: wraps non-JSON text under `note`).
 - Observability: Failures logged with structured logger; Discord user gets a
	 concise status response.

Running the bot:
	Normal mode: If `ENABLE_DISCORD_BOT=true` the FastAPI app lifecycle will
	automatically invoke `start_discord_bot()` during startup (non-blocking).
	Set these environment variables:
		ENABLE_DISCORD_BOT=true
		DISCORD_BOT_TOKEN=your_token_here
		BOT_INTERNAL_TOKEN=internal_submission_secret
		API_BASE_URL=http://localhost:8000/api/v1
		(optional) DISCORD_COMMAND_GUILDS=123456789012345678,987654321098765432

	Manual standalone debug (optional):
		python -m app.services.discord_bot

Safety / Production Notes:
  - For production, constrain guild registrations to specific IDs to avoid
	global propagation delays while iterating.
  - Consider rate limiting at the command level and adding cooldowns.
  - Provide richer autocomplete for campaign / platform IDs by querying the
	API (future enhancement).
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Optional, Any

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from app.config import (
	ENABLE_DISCORD_BOT,
	DISCORD_BOT_TOKEN,
	DISCORD_COMMAND_GUILDS,
	API_BASE_URL,
	BOT_INTERNAL_TOKEN,
)
from app.database import SessionLocal
from app.models.db import User
from app.models.db.affiliate_reports import SubmissionMethod
from app.utils import get_logger

logger = get_logger(__name__)

# ------------------------------- Helpers ---------------------------------- #

def _discord_affiliate_exists(user: discord.abc.User | discord.Member) -> bool:
	"""Return True if an active affiliate with this discord user id exists."""
	db = SessionLocal()
	try:
		return db.query(User).filter(
			User.discord_user_id == str(user.id),
			User.is_active == True
		).first() is not None
	finally:
		db.close()


async def _api_request(
	method: str,
	path: str,
	discord_user_id: str,
	payload: Optional[dict] = None,
) -> tuple[bool, Any]:
	"""Execute an HTTP request to the backend API.

	Returns (success, data_or_error)."""
	url = f"{API_BASE_URL.rstrip('/')}{path}"
	if not BOT_INTERNAL_TOKEN:
		return False, {"error": "BOT_INTERNAL_TOKEN not configured"}
	headers = {
		"Authorization": f"Bot {BOT_INTERNAL_TOKEN}",
		"X-Discord-User-ID": discord_user_id,
		"Content-Type": "application/json",
	}
	timeout = aiohttp.ClientTimeout(total=30)
	async with aiohttp.ClientSession(timeout=timeout) as session:
		try:
			async with session.request(method, url, headers=headers, json=payload) as resp:
				text = await resp.text()
				try:
					data = json.loads(text) if text else {}
				except json.JSONDecodeError:
					data = {"raw": text}
				if 200 <= resp.status < 300:
					return True, data
				else:
					return False, data or {"status": resp.status, "error": text}
		except Exception as e:  # pragma: no cover - network issues
			logger.error("API request failed", method=method, url=url, error=str(e))
			return False, {"error": str(e)}


def _parse_evidence(raw: Optional[str]) -> Optional[dict]:
	if not raw:
		return None
	try:
		return json.loads(raw)
	except json.JSONDecodeError:
		return {"note": raw}


# ------------------------------- Bot Setup -------------------------------- #

intents = discord.Intents.none()
bot = commands.Bot(command_prefix="!", intents=intents)  # prefix unused; we rely on slash cmds
_bot_started: bool = False


async def _ensure_guild_commands():
	if DISCORD_COMMAND_GUILDS:
		for gid in DISCORD_COMMAND_GUILDS:
			try:
				guild = discord.Object(id=gid)
				bot.tree.copy_global_to(guild=guild)
				await bot.tree.sync(guild=guild)
				logger.info("Synced commands to guild", guild_id=gid)
			except Exception as e:  # pragma: no cover
				logger.error("Guild command sync failed", guild_id=gid, error=str(e))
	else:
		try:
			await bot.tree.sync()
			logger.info("Synced global application commands")
		except Exception as e:  # pragma: no cover
			logger.error("Global command sync failed", error=str(e))


@bot.event
async def on_ready():  # pragma: no cover - event side effects
	logger.info("Discord bot logged in", bot_user=str(bot.user), id=bot.user.id if bot.user else None)
	await _ensure_guild_commands()


# ----------------------------- Slash Commands ----------------------------- #

@bot.tree.command(name="submit_post", description="Submit a new post with metrics")
@app_commands.describe(
	campaign_id="Campaign numeric ID",
	platform_id="Platform numeric ID",
	post_url="Full URL of the post",
	claimed_views="Claimed views (integer)",
	claimed_clicks="Claimed clicks (integer)",
	claimed_conversions="Claimed conversions (integer)",
	title="Optional post title",
	description="Optional post description",
	evidence_json="Optional JSON evidence payload"
)
async def submit_post_cmd(
	interaction: discord.Interaction,
	campaign_id: int,
	platform_id: int,
	post_url: str,
	claimed_views: int,
	claimed_clicks: int,
	claimed_conversions: int,
	title: Optional[str] = None,
	description: Optional[str] = None,
	evidence_json: Optional[str] = None,
):
	await interaction.response.defer(thinking=True, ephemeral=True)
	if not _discord_affiliate_exists(interaction.user):
		await interaction.followup.send("You are not linked to an affiliate account. Please contact support.")
		return

	payload = {
		"campaign_id": campaign_id,
		"platform_id": platform_id,
		"post_url": post_url,
		"claimed_views": claimed_views,
		"claimed_clicks": claimed_clicks,
		"claimed_conversions": claimed_conversions,
		"submission_method": SubmissionMethod.DISCORD.value,
	}
	if title:
		payload["title"] = title
	if description:
		payload["description"] = description
	evidence = _parse_evidence(evidence_json)
	if evidence:
		payload["evidence_data"] = evidence

	ok, data = await _api_request("POST", "/submissions/", str(interaction.user.id), payload)
	if ok:
		msg = data.get("message", "Submission accepted")
		post_id = data.get("data", {}).get("post_id") if isinstance(data, dict) else None
		await interaction.followup.send(f"✅ {msg} (post_id={post_id})")
	else:
		detail = data.get("message") if isinstance(data, dict) else data
		await interaction.followup.send(f"❌ Submission failed: {detail}")


@bot.tree.command(name="update_post", description="Update metrics for an existing post")
@app_commands.describe(
	post_id="Existing post ID",
	post_url="Original post URL (must match existing)",
	claimed_views="Updated claimed views",
	claimed_clicks="Updated claimed clicks",
	claimed_conversions="Updated claimed conversions",
	campaign_id="Original campaign id (for validation)",
	platform_id="Original platform id (for validation)",
	title="Updated title (optional)",
	description="Updated description (optional)",
	evidence_json="Optional JSON evidence"
)
async def update_post_cmd(
	interaction: discord.Interaction,
	post_id: int,
	post_url: str,
	claimed_views: int,
	claimed_clicks: int,
	claimed_conversions: int,
	campaign_id: int,
	platform_id: int,
	title: Optional[str] = None,
	description: Optional[str] = None,
	evidence_json: Optional[str] = None,
):
	await interaction.response.defer(thinking=True, ephemeral=True)
	if not _discord_affiliate_exists(interaction.user):
		await interaction.followup.send("You are not linked to an affiliate account. Please contact support.")
		return

	payload = {
		"campaign_id": campaign_id,
		"platform_id": platform_id,
		"post_url": post_url,
		"claimed_views": claimed_views,
		"claimed_clicks": claimed_clicks,
		"claimed_conversions": claimed_conversions,
		"submission_method": SubmissionMethod.DISCORD.value,
	}
	if title:
		payload["title"] = title
	if description:
		payload["description"] = description
	evidence = _parse_evidence(evidence_json)
	if evidence:
		payload["evidence_data"] = evidence

	ok, data = await _api_request("PUT", f"/submissions/{post_id}/metrics", str(interaction.user.id), payload)
	if ok:
		msg = data.get("message", "Update accepted")
		await interaction.followup.send(f"✅ {msg} (post_id={post_id})")
	else:
		detail = data.get("message") if isinstance(data, dict) else data
		await interaction.followup.send(f"❌ Update failed: {detail}")


# ------------------------------ Entry Point ------------------------------- #

async def start_discord_bot() -> None:
	"""Start the Discord bot asynchronously if enabled.

	Safe to call multiple times; only first invocation starts the client.
	"""
	global _bot_started
	if _bot_started:
		return
	if not ENABLE_DISCORD_BOT:
		logger.info("Discord bot not enabled; skipping startup")
		return
	if not DISCORD_BOT_TOKEN:
		logger.error("Cannot start Discord bot: DISCORD_BOT_TOKEN missing")
		return
	logger.info(
		"Launching Discord bot",
		guild_scope="guilds" if DISCORD_COMMAND_GUILDS else "global",
		api_base=API_BASE_URL,
	)
	_bot_started = True
	# create background task to run the bot; discord.py provides start() for awaitable use
	asyncio.create_task(bot.start(DISCORD_BOT_TOKEN))


async def stop_discord_bot() -> None:
	"""Stop the Discord bot if it was started."""
	global _bot_started
	if _bot_started and bot.is_closed() is False:
		try:
			await bot.close()
			logger.info("Discord bot closed successfully")
		finally:
			_bot_started = False


if __name__ == "__main__":  # pragma: no cover
	# Fallback manual run for local debugging
	asyncio.run(start_discord_bot())
	try:
		asyncio.get_event_loop().run_forever()
	except KeyboardInterrupt:  # pragma: no cover
		asyncio.run(stop_discord_bot())

