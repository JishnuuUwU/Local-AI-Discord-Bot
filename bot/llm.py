"""
Local LLM Inference Engine
==========================
Interfaces with local OpenAI-compatible endpoints (Ollama, OpenVINO, vLLM).
Enforces hardware bounds, low token limits, and failure circuit-breaking.
"""

from __future__ import annotations

import asyncio
import time
from typing import Dict, List, Optional

import aiohttp

from bot.config import (
    INFERENCE_TIMEOUT,
    MAX_TOKENS,
    SYSTEM_PERSONA,
    TEMPERATURE,
    TOP_P,
    logger,
)


def resolve_chat_endpoint(base_or_full_url: str) -> str:
    """
    Normalizes local inference base URLs to the standard OpenAI-compatible
    chat completions endpoint (/v1/chat/completions).
    """
    url = base_or_full_url.rstrip("/")
    if url.endswith("/chat/completions"):
        return url
    if url.endswith("/v1"):
        return f"{url}/chat/completions"
    return f"{url}/v1/chat/completions"


class LocalLLMClient:
    """
    Async client for OpenAI-compatible local endpoints (Ollama, OpenVINO, vLLM).
    Enforces hardware bounds, low token limits, and failure circuit-breaking.
    """

    def __init__(self, endpoint_url: str, model_name: str, session: Optional[aiohttp.ClientSession] = None):
        self.endpoint_url = resolve_chat_endpoint(endpoint_url)
        self.model_name = model_name
        self.session = session

    async def generate_response(self, user_prompt: str, context: Optional[str] = None) -> str:
        """
        Sends structured chat completions request with strict VRAM-conserving parameters.
        Returns parsed assistant text or detailed diagnostics on failure.
        """
        if not self.session:
            return "Internal Error: HTTP client session is not initialized."

        messages: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PERSONA}]

        if context and context.strip():
            user_content = (
                f"[Real-Time Web Context]\n"
                f"{context.strip()}\n\n"
                f"[User Query]\n"
                f"{user_prompt}"
            )
        else:
            user_content = user_prompt

        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "max_tokens": MAX_TOKENS,
            "stream": False,
        }

        timeout = aiohttp.ClientTimeout(total=INFERENCE_TIMEOUT)

        try:
            start_time = time.perf_counter()
            async with self.session.post(self.endpoint_url, json=payload, timeout=timeout) as resp:
                elapsed = time.perf_counter() - start_time

                if resp.status == 200:
                    data = await resp.json()
                    choices = data.get("choices", [])
                    if not choices:
                        return "Warning: Local model returned an empty choices payload."
                    raw_text = choices[0].get("message", {}).get("content", "")
                    logger.info("Inference completed in %.2fs (Model: %s)", elapsed, self.model_name)
                    return raw_text.strip()

                error_body = await resp.text()
                logger.error("Local LLM HTTP %d Error: %s", resp.status, error_body)

                if resp.status == 404:
                    return (
                        f"Error (HTTP 404): Model '{self.model_name}' was not found at `{self.endpoint_url}`.\n"
                        f"Please run `ollama pull {self.model_name}` or verify `MODEL_NAME` in your `.env`."
                    )
                if resp.status == 500:
                    return (
                        "Error (HTTP 500): Local backend encountered an internal error.\n"
                        "Check your local inference server logs for VRAM Out-of-Memory (OOM) or compute crashes."
                    )
                return f"Error: Local inference backend returned HTTP {resp.status}: {error_body[:200]}"

        except asyncio.TimeoutError:
            logger.error("Inference timed out after %.1fs", INFERENCE_TIMEOUT)
            return (
                f"Inference Timeout: Local backend took longer than {INFERENCE_TIMEOUT:.0f}s to generate tokens.\n"
                "Hardware may be bottlenecked or paging model layers between VRAM and system RAM."
            )
        except aiohttp.ClientConnectorError as exc:
            logger.error("Connection failed to %s: %s", self.endpoint_url, exc)
            return (
                f"Connection Refused: Unable to reach local inference backend at `{self.endpoint_url}`.\n"
                "Ensure your local model server (Ollama, OpenVINO, or LM Studio) is running."
            )
        except Exception as exc:
            logger.exception("Unexpected error during local inference: %s", exc)
            return f"Inference Error: Unexpected exception occurred: {exc}"
