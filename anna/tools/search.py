"""Web search tool — lets Anna look up real-time information.

Uses DuckDuckGo (no API key needed) to search the web and return
relevant snippets that Anna can use to answer questions.
"""

from __future__ import annotations

import re
import requests
from anna.core.config import logger

_DDG_URL = "https://api.duckduckgo.com/"
_HEADERS = {
    "User-Agent": "Anna/1.0 (Personal Assistant Bot)",
}

# Patterns that suggest the user wants real-time or factual info
_SEARCH_PATTERNS = [
    r"\b(price of|how much is|what is the price)\b",
    r"\b(btc|bitcoin|eth|ethereum|crypto|stock|stocks)\b.*\b(price|worth|cost|value)\b",
    r"\b(weather in|weather for|temperature in)\b",
    r"\b(what is|what are|who is|who are|what was|who was)\b",
    r"\b(when is|when was|when did|when does)\b",
    r"\b(where is|where are|where was)\b",
    r"\b(latest|current|recent|today|news about)\b",
    r"\b(look up|search for|google|find out about)\b",
    r"\b(how many|how much|how old|how tall|how far)\b",
    r"\b(define|definition of|meaning of)\b",
    r"\b(score|results|game|match)\b.*\b(today|last night|yesterday)\b",
]


def needs_search(text: str) -> bool:
    """Check if a message would benefit from a web search."""
    text_lower = text.lower().strip()

    # Very short casual messages don't need search
    if len(text_lower.split()) <= 2:
        return False

    for pattern in _SEARCH_PATTERNS:
        if re.search(pattern, text_lower):
            return True

    return False


def search(query: str, max_results: int = 3) -> str:
    """Search the web and return a condensed result string.

    Returns a string of search results that can be injected into
    the AI context, or empty string if search fails.
    """
    results = []

    # Try DuckDuckGo Instant Answer API first
    instant = _ddg_instant(query)
    if instant:
        results.append(instant)

    # Try DuckDuckGo HTML search for more results
    web_results = _ddg_web_search(query, max_results)
    results.extend(web_results)

    if not results:
        return ""

    return "\n".join(results[:max_results])


def _ddg_instant(query: str) -> str | None:
    """Try DuckDuckGo Instant Answer API."""
    try:
        resp = requests.get(
            _DDG_URL,
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            headers=_HEADERS,
            timeout=5,
        )
        data = resp.json()

        # Abstract (Wikipedia-style answer)
        if data.get("AbstractText"):
            return data["AbstractText"]

        # Answer (direct computation/fact)
        if data.get("Answer"):
            return str(data["Answer"])

        # Related topics
        if data.get("RelatedTopics"):
            for topic in data["RelatedTopics"][:2]:
                if isinstance(topic, dict) and topic.get("Text"):
                    return topic["Text"]

    except Exception as e:
        logger.warning(f"DDG instant search failed: {e}")

    return None


def _ddg_web_search(query: str, max_results: int = 3) -> list[str]:
    """Search DuckDuckGo HTML and extract result snippets."""
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=_HEADERS,
            timeout=5,
        )

        if resp.status_code != 200:
            return []

        # Simple regex extraction from DDG HTML results
        snippets = re.findall(
            r'class="result__snippet"[^>]*>(.*?)</a>',
            resp.text,
            re.DOTALL,
        )

        results = []
        for snippet in snippets[:max_results]:
            # Clean HTML tags
            clean = re.sub(r"<[^>]+>", "", snippet).strip()
            if clean and len(clean) > 20:
                results.append(clean)

        return results

    except Exception as e:
        logger.warning(f"DDG web search failed: {e}")
        return []
