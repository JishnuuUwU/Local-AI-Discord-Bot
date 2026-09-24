"""
Bot Core Module
===============
Manages client lifecycle, connection pools, event routing,
and Discord user command dispatching.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
from typing import Optional

import aiohttp
import discord
from discord.ext import commands

from bot.config import (
    COMMAND_PREFIX,
    DISCORD_TOKEN,
    INFERENCE_TIMEOUT,
    LOCAL_LLM_URL,
    MAX_TOKENS,
    MODEL_NAME,
    SEARCH_ENABLED,
    SYSTEM_PERSONA,
    TEMPERATURE,
    logger,
)
from bot.chunker import chunk_message
from bot.scraper import DuckDuckGoScraper
from bot.llm import LocalLLMClient


class Bot(commands.Bot):
    """
    Discord Bot client managing connection pools, intent gating,
    event processing, and graceful shutdown lifecycles.
    """

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Requires Message Content Intent in Discord Developer Portal

        super().__init__(
            command_prefix=COMMAND_PREFIX,
            intents=intents,
            help_command=None,
        )

        self.http_session: Optional[aiohttp.ClientSession] = None
        self.scraper = DuckDuckGoScraper()
        self.llm_client = LocalLLMClient(LOCAL_LLM_URL, MODEL_NAME)
        self.start_time = time.time()

    async def setup_hook(self):
        """Initializes shared aiohttp.ClientSession with TCP connection pooling."""
        connector = aiohttp.TCPConnector(limit=15, keepalive_timeout=60.0)
        timeout = aiohttp.ClientTimeout(total=INFERENCE_TIMEOUT + 15.0)
        self.http_session = aiohttp.ClientSession(connector=connector, timeout=timeout)

        self.scraper.session = self.http_session
        self.llm_client.session = self.http_session

        logger.info("Shared async HTTP session and TCP connection pool established.")

    async def close(self):
        """Performs clean shutdown and closes TCP connection pools."""
        logger.info("Closing bot and draining active network sessions...")
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
        await super().close()


bot = Bot()


# ==============================================================================
# EVENT HANDLERS
# ==============================================================================
@bot.event
async def on_ready():
    logger.info("=" * 60)
    logger.info("Bot logged in as: %s (ID: %s)", bot.user, bot.user.id if bot.user else "Unknown")
    logger.info("Active Target Model : %s", MODEL_NAME)
    logger.info("Inference Endpoint  : %s", bot.llm_client.endpoint_url)
    logger.info("Max Tokens Capped   : %d", MAX_TOKENS)
    logger.info("Web Search Enabled  : %s", SEARCH_ENABLED)
    logger.info("=" * 60)


@bot.event
async def on_message(message: discord.Message):
    # Ignore messages originating from bots (including self)
    if message.author.bot:
        return

    # Trigger via direct bot mention or Direct Message
    is_mentioned = bot.user in message.mentions if bot.user else False
    is_dm = isinstance(message.channel, discord.DMChannel)

    # Allow prefix commands to pass through to command processor
    if message.content.startswith(COMMAND_PREFIX):
        await bot.process_commands(message)
        return

    if is_mentioned or is_dm:
        # Strip mention tags cleanly: <@ID>, <@!ID>, or @BotName
        clean_prompt = message.content
        if bot.user:
            clean_prompt = re.sub(rf"<@!?{bot.user.id}>", "", clean_prompt)
            clean_prompt = clean_prompt.replace(f"@{bot.user.name}", "")
        clean_prompt = clean_prompt.strip()

        # Guard: Prevent empty prompt processing
        if not clean_prompt:
            hint = (
                f"Hello {message.author.mention}! Mention me with a query or use `{COMMAND_PREFIX}ask <prompt>`.\n"
                f"Use `{COMMAND_PREFIX}search <query>` to force real-time web context."
            )
            await message.reply(hint, mention_author=False)
            return

        await handle_generation(message, clean_prompt)


async def handle_generation(message: discord.Message, prompt: str, force_search: bool = False):
    """
    Coordinates web context extraction, local LLM generation, validation checks,
    and safe Discord message chunking.
    """
    async with message.channel.typing():
        # Web context injection
        context = ""
        if force_search or bot.scraper.should_search(prompt):
            search_query = re.sub(r"^(search|lookup|find|browse)\s+(for\s+)?", "", prompt, flags=re.I).strip()
            search_query = search_query or prompt
            context = await bot.scraper.fetch_snippets(search_query)

        # Query local LLM
        reply = await bot.llm_client.generate_response(prompt, context)

        # STRICT VALIDATION: Prevent Discord HTTP 400 Bad Request error (50035: Cannot send empty message)
        if not reply or not reply.strip():
            reply = "⚠️ The local model finished inference with an empty output token sequence."

        # Discord safe message chunking (2000 character limit enforcement)
        chunks = chunk_message(reply, max_chars=1900)
        if not chunks:
            chunks = ["⚠️ Unable to format response."]

        try:
            # First chunk replies to original message
            await message.reply(chunks[0], mention_author=False)

            # Subsequent chunks sent to channel
            for chunk in chunks[1:]:
                await message.channel.send(chunk)
        except discord.Forbidden:
            logger.error("Missing permissions to send message in channel %s", message.channel)
        except discord.HTTPException as exc:
            logger.error("Discord HTTP error sending message: %s", exc)


# ==============================================================================
# USER COMMANDS
# ==============================================================================
@bot.command(name="ask", help="Query the local LLM directly.")
async def ask_command(ctx: commands.Context, *, prompt: str = ""):
    """Explicit command to query the local LLM."""
    if not prompt.strip():
        await ctx.reply(f"Usage: `{COMMAND_PREFIX}ask <your prompt here>`", mention_author=False)
        return
    await handle_generation(ctx.message, prompt.strip(), force_search=False)


@bot.command(name="search", help="Force DuckDuckGo web search context grounding.")
async def search_command(ctx: commands.Context, *, query: str = ""):
    """Forces web search and grounds the local LLM response."""
    if not query.strip():
        await ctx.reply(f"Usage: `{COMMAND_PREFIX}search <query to research>`", mention_author=False)
        return
    await handle_generation(ctx.message, query.strip(), force_search=True)


@bot.command(name="status", help="Check local LLM connectivity, model, and resource parameters.")
async def status_command(ctx: commands.Context):
    """Provides operational diagnostics and backend latency checks."""
    uptime_sec = int(time.time() - bot.start_time)
    hours, rem = divmod(uptime_sec, 3600)
    minutes, seconds = divmod(rem, 60)

    # Perform lightweight ping to local inference endpoint
    latency_str = "Checking..."
    health_status = "🟢 Online"

    if bot.http_session:
        try:
            start_ping = time.perf_counter()
            test_url = LOCAL_LLM_URL.replace("/chat/completions", "").rstrip("/")
            async with bot.http_session.get(test_url, timeout=aiohttp.ClientTimeout(total=3.0)) as resp:
                elapsed_ms = (time.perf_counter() - start_ping) * 1000
                latency_str = f"{elapsed_ms:.1f} ms (HTTP {resp.status})"
        except Exception:
            health_status = "🔴 Unreachable"
            latency_str = "N/A"
    else:
        health_status = "🔴 Session Offline"

    status_msg = (
        f"**Local AI Bot System Diagnostics**\n"
        f"```yaml\n"
        f"Backend Status  : {health_status}\n"
        f"Endpoint URL    : {bot.llm_client.endpoint_url}\n"
        f"Active Model    : {MODEL_NAME}\n"
        f"Probe Latency   : {latency_str}\n"
        f"VRAM Ceiling    : < 5.0 GB (Optimized for edge/quantized weights)\n"
        f"Max Tokens Cap  : {MAX_TOKENS}\n"
        f"Sampling Temp   : {TEMPERATURE}\n"
        f"Search Scraper  : {'Enabled (Zero API Key)' if SEARCH_ENABLED else 'Disabled'}\n"
        f"Bot Uptime      : {hours:02d}h {minutes:02d}m {seconds:02d}s\n"
        f"```"
    )
    await ctx.reply(status_msg, mention_author=False)


@bot.command(name="persona", help="Display the current active system persona prompt.")
async def persona_command(ctx: commands.Context):
    """Displays the active persona guidelines."""
    msg = (
        f"**Active System Persona:**\n"
        f"```markdown\n{SYSTEM_PERSONA}\n```"
    )
    await ctx.reply(msg, mention_author=False)


@bot.command(name="help", help="Display help and usage guidelines.")
async def help_command(ctx: commands.Context):
    """Clean, structured help reference."""
    help_text = (
        f"**Local AI Bot - Privacy-Focused Local Assistant**\n\n"
        f"**How to interact:**\n"
        f"• Mention `{bot.user.mention if bot.user else '@Bot'} <prompt>` anywhere in authorized channels.\n"
        f"• Send a **Direct Message (DM)** to the bot.\n"
        f"• Use `{COMMAND_PREFIX}ask <prompt>` to run a query.\n"
        f"• Use `{COMMAND_PREFIX}search <query>` to force DuckDuckGo real-time web context grounding.\n"
        f"• Use `{COMMAND_PREFIX}status` to inspect local LLM connectivity, latency, and VRAM profile.\n"
        f"• Use `{COMMAND_PREFIX}persona` to view the active system prompt.\n\n"
        f"*100% Local Inference — Zero external telemetry or cloud token fees.*"
    )
    await ctx.reply(help_text, mention_author=False)


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception):
    """Graceful command error handler."""
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore unknown commands
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(f"⚠️ Missing argument. Use `{COMMAND_PREFIX}help` for usage.", mention_author=False)
        return
    logger.error("Command error on %s: %s", ctx.command, error)


# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================
def main():
    if not DISCORD_TOKEN or DISCORD_TOKEN == "YOUR_DISCORD_BOT_TOKEN":
        logger.error("=" * 60)
        logger.error("CRITICAL CONFIGURATION ERROR:")
        logger.error("DISCORD_BOT_TOKEN is not set or contains default placeholder.")
        logger.error("Set DISCORD_BOT_TOKEN in your .env file or environment variables.")
        logger.error("=" * 60)
        sys.exit(1)

    try:
        bot.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.error("Discord Login Failure: Invalid or expired bot token.")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as exc:
        logger.exception("Fatal runtime error in bot lifecycle: %s", exc)
        sys.exit(1)
