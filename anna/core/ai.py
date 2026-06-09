"""AI provider setup with automatic failover.

Provider priority: OpenRouter (primary) -> Groq (fallback #1) -> Cerebras (fallback #2).
All providers expose a common `chat(messages, system_prompt)` interface.
"""

from __future__ import annotations

from typing import Optional

from anna.core.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    GROQ_API_KEY,
    CEREBRAS_API_KEY,
    logger,
)


class AIProvider:
    """Unified interface to LLM providers with automatic failover."""

    def __init__(self):
        self._providers: list[dict] = []
        self._setup_providers()

    def _setup_providers(self):
        if OPENROUTER_API_KEY:
            try:
                from openai import OpenAI as OpenRouterClient
                import httpx

                transport = httpx.HTTPTransport(retries=1)
                http_client = httpx.Client(transport=transport, timeout=10.0)
                client = OpenRouterClient(
                    api_key=OPENROUTER_API_KEY,
                    base_url="https://openrouter.ai/api/v1",
                    http_client=http_client,
                )
                self._providers.append({
                    "name": "openrouter",
                    "client": client,
                    "model": OPENROUTER_MODEL,
                })
                logger.info("OpenRouter connected as PRIMARY")
            except Exception as e:
                logger.error(f"OpenRouter setup failed: {e}")

        if GROQ_API_KEY:
            try:
                from groq import Groq

                client = Groq(api_key=GROQ_API_KEY)
                self._providers.append({
                    "name": "groq",
                    "client": client,
                    "model": "llama-3.3-70b-versatile",
                })
                logger.info("Groq connected as fallback #1")
            except Exception as e:
                logger.error(f"Groq setup failed: {e}")

        if CEREBRAS_API_KEY:
            try:
                from openai import OpenAI as CerebrasClient

                client = CerebrasClient(
                    api_key=CEREBRAS_API_KEY,
                    base_url="https://api.cerebras.ai/v1",
                )
                self._providers.append({
                    "name": "cerebras",
                    "client": client,
                    "model": "llama-3.3-70b",
                })
                logger.info("Cerebras connected as fallback #2")
            except Exception as e:
                logger.error(f"Cerebras setup failed: {e}")

        if not self._providers:
            logger.warning("No AI provider configured.")

    @property
    def available(self) -> bool:
        return len(self._providers) > 0

    def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        max_tokens: int = 512,
    ) -> Optional[str]:
        """Send a chat completion request, falling through providers on failure."""
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        for provider in self._providers:
            try:
                response = provider["client"].chat.completions.create(
                    model=provider["model"],
                    messages=messages,
                    max_tokens=max_tokens,
                )
                text = response.choices[0].message.content
                if text:
                    return text.strip()
            except Exception as e:
                logger.warning(f"{provider['name']} failed: {e}")
                continue

        logger.error("All AI providers failed.")
        return None


# Singleton
ai = AIProvider()
