"""Discord bot interface for affiliate submissions.

Provides slash commands that proxy to the FastAPI backend so affiliates can
submit and update post metrics directly from Discord.

Key design points:
 - Authorization: We map a Discord user (author.id) to an Affiliate record via
   the `affiliates.discord_user_id` column. This column should store the raw
   numeric Discord user id as a string (recommended) OR a legacy username tag.
   We first attempt numeric id match; if not found we fallback to a case
   insensitive match on the value in the column.
 - API Calls: Uses aiohttp to call the backend submissions endpoints:
	 POST   /api/v1/submissions            -> create new post
	 PUT    /api/v1/submissions/{post_id}/metrics -> update metrics
   The backend requires Bearer API key auth, so once we resolve the affiliate
   we obtain their api_key from DB and pass it in Authorization header.
 - Evidence: For simplicity, evidence is accepted as an optional JSON snippet
   (string) which we attempt to parse. If parsing fails we ignore it with a
   gentle warning to the user.
 - Error Handling: We surface concise error messages to Discord but log full
   details locally using the platform's structured logger.

Running the bot:
  Set the following environment variables (see .env.example):
	ENABLE_DISCORD_BOT=true
	DISCORD_BOT_TOKEN=your_token_here
	API_BASE_URL=http://localhost:8000/api/v1
	(optional) DISCORD_COMMAND_GUILDS=123456789012345678,987654321098765432

  Then execute (separate process from the FastAPI app):
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
)
from app.database import SessionLocal
from app.models.db import Affiliate
from app.models.db.affiliate_reports import SubmissionMethod
from app.utils import get_logger

logger = get_logger(__name__)

# ------------------------------- Helpers ---------------------------------- #

def _get_affiliate_by_discord(user: discord.abc.User | discord.Member) -> Optional[Affiliate]:
	"""Lookup affiliate by discord user id or legacy tag.

	We expect `Affiliate.discord_user_id` to store the numeric snowflake as
	string. For backward compatibility we also attempt a case-insensitive
	comparison against the stored value (covers old username#discrim style).
	"""
	db = SessionLocal()
	try:
		user_id_str = str(user.id)
		affiliate = (
			db.query(Affiliate)
			.filter(Affiliate.discord_user_id == user_id_str, Affiliate.is_active == True)
			.first()
		)
		if affiliate:
			return affiliate
		# fallback legacy (case insensitive)
		# WARNING: This is less performant; acceptable for MVP scale.
		legacy = (
			db.query(Affiliate)
			.filter(Affiliate.is_active == True)
			.filter(Affiliate.discord_user_id != None)  # type: ignore
			.all()
		)
		for aff in legacy:
			if aff.discord_user_id and aff.discord_user_id.lower() == user_id_str.lower():
				return aff
		return None
	finally:
		db.close()


async def _api_request(
	method: str,
	path: str,
	api_key: Optional[str],
	payload: Optional[dict] = None,
) -> tuple[bool, Any]:
	"""Execute an HTTP request to the backend API.

	Returns (success, data_or_error)."""
	if not api_key:
		return False, {"error": "Affiliate has no API key configured"}
	url = f"{API_BASE_URL.rstrip('/')}{path}"
	headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
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
	affiliate = _get_affiliate_by_discord(interaction.user)
	if not affiliate:
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

	ok, data = await _api_request("POST", "/submissions/", affiliate.api_key, payload)
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
	affiliate = _get_affiliate_by_discord(interaction.user)
	if not affiliate:
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

	ok, data = await _api_request("PUT", f"/submissions/{post_id}/metrics", affiliate.api_key, payload)
	if ok:
		msg = data.get("message", "Update accepted")
		await interaction.followup.send(f"✅ {msg} (post_id={post_id})")
	else:
		detail = data.get("message") if isinstance(data, dict) else data
		await interaction.followup.send(f"❌ Update failed: {detail}")


# ------------------------------ Entry Point ------------------------------- #

def main() -> None:  # pragma: no cover - runtime entry
	if not ENABLE_DISCORD_BOT:
		logger.warning("Discord bot disabled. Set ENABLE_DISCORD_BOT=true to run.")
		return
	if not DISCORD_BOT_TOKEN:
		logger.error("DISCORD_BOT_TOKEN not provided. Bot cannot start.")
		return
	logger.info(
		"Starting Discord bot",
		guild_scope="guilds" if DISCORD_COMMAND_GUILDS else "global",
		api_base=API_BASE_URL,
	)
	bot.run(DISCORD_BOT_TOKEN)  # blocking


if __name__ == "__main__":  # pragma: no cover
	main()

