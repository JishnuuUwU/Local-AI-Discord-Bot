"""
Web Scraping & Context Pipeline
===============================
Zero-API-key search scraper targeting DuckDuckGo HTML.
Extracts top snippet results and enforces strict character limits
to avoid bloating the LLM's limited VRAM KV-cache context.
"""

from __future__ import annotations

import asyncio
import re
from typing import List, Optional
from urllib.parse import parse_qs, quote_plus, urlparse

import aiohttp
from bs4 import BeautifulSoup

from bot.config import (
    MAX_SNIPPET_LENGTH,
    SEARCH_ENABLED,
    SEARCH_MAX_RESULTS,
    SEARCH_TIMEOUT,
    logger,
)


class DuckDuckGoScraper:
    """
    Zero-API-key web context scraper targeting DuckDuckGo HTML.
    Extracts top snippet results and enforces strict character limits.
    """

    SEARCH_ENDPOINT = "https://html.duckduckgo.com/html/"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://html.duckduckgo.com/",
    }

    # Temporal & real-time intent triggers
    SEARCH_TRIGGERS = [
        re.compile(r"\b(today|tonight|yesterday|tomorrow|now|currently|current|latest|recent|recently|newest)\b", re.I),
        re.compile(r"\b(news|weather|stock|stocks|price|rates|crypto|btc|eth|patch|update|release|earnings)\b", re.I),
        re.compile(r"\b(who is currently|what happened|what is the price of|who won|score)\b", re.I),
        re.compile(r"^(search|lookup|browse|find)\b", re.I),
    ]

    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self.session = session

    def should_search(self, prompt: str) -> bool:
        """Determines if a prompt requires real-time web context injection."""
        if not SEARCH_ENABLED or not prompt:
            return False
        clean = prompt.lower().strip()
        return any(trigger.search(clean) is not None for trigger in self.SEARCH_TRIGGERS)

    def _extract_target_url(self, raw_href: str) -> str:
        """Decodes target destination from DuckDuckGo redirect link."""
        if not raw_href:
            return ""
        if "duckduckgo.com/l/?" in raw_href or raw_href.startswith("/l/?"):
            parsed = urlparse(raw_href)
            params = parse_qs(parsed.query)
            if "uddg" in params:
                return params["uddg"][0]
        if raw_href.startswith("//"):
            return f"https:{raw_href}"
        return raw_href

    async def fetch_snippets(self, query: str, max_results: int = SEARCH_MAX_RESULTS) -> str:
        """
        Executes non-blocking HTML search and returns structured, capped snippets.
        Guarantees zero memory explosion by truncating snippets.
        """
        if not self.session:
            logger.warning("Scraper invoked without active aiohttp session.")
            return ""

        url = f"{self.SEARCH_ENDPOINT}?q={quote_plus(query)}"
        timeout = aiohttp.ClientTimeout(total=SEARCH_TIMEOUT)

        try:
            async with self.session.get(url, headers=self.HEADERS, timeout=timeout) as response:
                if response.status != 200:
                    logger.warning("DuckDuckGo HTML search returned HTTP %s", response.status)
                    return ""
                html = await response.text(encoding="utf-8", errors="ignore")
        except asyncio.TimeoutError:
            logger.warning("Web search timed out for query: %s", query)
            return ""
        except Exception as exc:
            logger.warning("Web search request failed: %s", exc)
            return ""

        # Parse lightweight HTML
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        results: List[str] = []
        body_elements = soup.find_all("div", class_="result__body")

        for elem in body_elements:
            if len(results) >= max_results:
                break

            title_elem = elem.find("a", class_="result__a")
            snippet_elem = elem.find("a", class_="result__snippet") or elem.find("div", class_="result__snippet")

            if not snippet_elem:
                continue

            title = title_elem.get_text(strip=True) if title_elem else "Source"
            snippet = snippet_elem.get_text(separator=" ", strip=True)
            snippet = re.sub(r"\s+", " ", snippet)

            if len(snippet) > MAX_SNIPPET_LENGTH:
                snippet = snippet[:MAX_SNIPPET_LENGTH].rstrip() + "..."

            link = self._extract_target_url(title_elem["href"]) if title_elem and title_elem.has_attr("href") else ""

            if snippet:
                formatted = f"- Title: {title}\n  Snippet: {snippet}"
                if link:
                    formatted += f"\n  Source: {link}"
                results.append(formatted)

        if not results:
            return ""

        logger.info("Retrieved %d web snippets for query: '%s'", len(results), query[:50])
        return "\n\n".join(results)
