"""
Bot Configuration Module
========================
Centralized settings, hardware constraints, and modular persona definition.
Loads parameters from the environment and local .env file.
"""

from __future__ import annotations

import logging
import os
from dotenv import load_dotenv

# Load local environment configuration from .env file
load_dotenv()

# ==============================================================================
# LOGGING CONFIGURATION
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("bot")

# ==============================================================================
# MODULAR SYSTEM PERSONA
# ==============================================================================
DEFAULT_SYSTEM_PERSONA = (
    "You are a fast, knowledgeable, and privacy-conscious local AI assistant. "
    "You operate entirely on private local hardware with zero external telemetry.\n\n"
    "Guidelines:\n"
    "1. Deliver direct, concise, and technically accurate responses.\n"
    "2. Avoid generic conversational fluff, filler preambles, and excessive disclaimers.\n"
    "3. When real-time web context is provided, prioritize it for up-to-date facts.\n"
    "4. Format code, commands, and technical steps cleanly using standard Markdown."
)

SYSTEM_PERSONA: str = os.getenv("SYSTEM_PERSONA", DEFAULT_SYSTEM_PERSONA).strip()

# ==============================================================================
# TARGET MODEL & HARDWARE CONSTRAINTS (< 5GB VRAM CEILING)
# ==============================================================================
DISCORD_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "").strip()
LOCAL_LLM_URL: str = os.getenv("LOCAL_LLM_URL", "http://localhost:11434/v1").strip()
MODEL_NAME: str = os.getenv("MODEL_NAME", "gemma2:2b").strip()

# Low-latency capped token hyperparameters
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "512"))
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.7"))
TOP_P: float = float(os.getenv("TOP_P", "0.9"))
INFERENCE_TIMEOUT: float = float(os.getenv("INFERENCE_TIMEOUT_SECONDS", "60.0"))

# ==============================================================================
# WEB SCRAPING & COMMAND CONFIGURATION
# ==============================================================================
SEARCH_ENABLED: bool = os.getenv("SEARCH_ENABLED", "true").lower() in ("true", "1", "yes")
SEARCH_MAX_RESULTS: int = int(os.getenv("SEARCH_MAX_RESULTS", "3"))
SEARCH_TIMEOUT: float = float(os.getenv("SEARCH_TIMEOUT_SECONDS", "5.0"))
MAX_SNIPPET_LENGTH: int = int(os.getenv("MAX_SNIPPET_LENGTH", "250"))
COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", "!")
