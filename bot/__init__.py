"""
Bot Package
===========
Lightweight, Privacy-Focused Local AI Discord Bot.
"""

from bot.config import (
    COMMAND_PREFIX,
    DEFAULT_SYSTEM_PERSONA,
    DISCORD_TOKEN,
    INFERENCE_TIMEOUT,
    LOCAL_LLM_URL,
    MAX_SNIPPET_LENGTH,
    MAX_TOKENS,
    MODEL_NAME,
    SEARCH_ENABLED,
    SEARCH_MAX_RESULTS,
    SEARCH_TIMEOUT,
    SYSTEM_PERSONA,
    TEMPERATURE,
    TOP_P,
)
from bot.chunker import chunk_message
from bot.scraper import DuckDuckGoScraper
from bot.llm import LocalLLMClient, resolve_chat_endpoint
from bot.client import Bot, bot, main

__all__ = [
    "COMMAND_PREFIX",
    "DEFAULT_SYSTEM_PERSONA",
    "DISCORD_TOKEN",
    "INFERENCE_TIMEOUT",
    "LOCAL_LLM_URL",
    "MAX_SNIPPET_LENGTH",
    "MAX_TOKENS",
    "MODEL_NAME",
    "SEARCH_ENABLED",
    "SEARCH_MAX_RESULTS",
    "SEARCH_TIMEOUT",
    "SYSTEM_PERSONA",
    "TEMPERATURE",
    "TOP_P",
    "chunk_message",
    "DuckDuckGoScraper",
    "LocalLLMClient",
    "resolve_chat_endpoint",
    "Bot",
    "bot",
    "main",
]
