"""AI provider setup with automatic failover and smart routing.

Two tiers:
- "fast": Groq/Cerebras for casual chat (free, low latency)
- "smart": OpenRouter for complex questions (paid, higher quality)

Both tiers fall through to the next available provider on failure.
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
    """Unified interface to LLM providers with tiered routing and failover."""

    def __init__(self):
        self._smart_providers: list[dict] = []
        self._fast_providers: list[dict] = []
        self._setup_providers()

    def _setup_providers(self):
        # Smart tier: OpenRouter first (best quality)
        openrouter = self._init_openrouter()
        groq = self._init_groq()
        cerebras = self._init_cerebras()

        # Smart tier: OpenRouter → Groq → Cerebras
        if openrouter:
            self._smart_providers.append(openrouter)
        if groq:
            self._smart_providers.append(groq)
        if cerebras:
            self._smart_providers.append(cerebras)

        # Fast tier: Groq → Cerebras → OpenRouter (prefer free/fast providers)
        if groq:
            self._fast_providers.append(groq)
        if cerebras:
            self._fast_providers.append(cerebras)
        if openrouter:
            self._fast_providers.append(openrouter)

        if not self._smart_providers and not self._fast_providers:
            logger.warning("No AI provider configured.")

    def _init_openrouter(self) -> Optional[dict]:
        if not OPENROUTER_API_KEY:
            return None
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
            logger.info("OpenRouter connected (smart tier primary)")
            return {"name": "openrouter", "client": client, "model": OPENROUTER_MODEL}
        except Exception as e:
            logger.error(f"OpenRouter setup failed: {e}")
            return None

    def _init_groq(self) -> Optional[dict]:
        if not GROQ_API_KEY:
            return None
        try:
            from groq import Groq

            client = Groq(api_key=GROQ_API_KEY)
            logger.info("Groq connected (fast tier primary)")
            return {"name": "groq", "client": client, "model": "llama-3.3-70b-versatile"}
        except Exception as e:
            logger.error(f"Groq setup failed: {e}")
            return None

    def _init_cerebras(self) -> Optional[dict]:
        if not CEREBRAS_API_KEY:
            return None
        try:
            from openai import OpenAI as CerebrasClient

            client = CerebrasClient(
                api_key=CEREBRAS_API_KEY,
                base_url="https://api.cerebras.ai/v1",
            )
            logger.info("Cerebras connected (fast tier fallback)")
            return {"name": "cerebras", "client": client, "model": "llama-3.3-70b"}
        except Exception as e:
            logger.error(f"Cerebras setup failed: {e}")
            return None

    @property
    def available(self) -> bool:
        return len(self._smart_providers) > 0 or len(self._fast_providers) > 0

    def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        max_tokens: int = 512,
        tier: str = "smart",
    ) -> Optional[str]:
        """Send a chat completion request using the specified tier.

        tier="fast" → Groq/Cerebras first (free, low latency)
        tier="smart" → OpenRouter first (paid, higher quality)
        Both tiers fall through to the next provider on failure.
        """
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        providers = self._fast_providers if tier == "fast" else self._smart_providers

        # If preferred tier has no providers, fall back to whatever is available
        if not providers:
            providers = self._smart_providers or self._fast_providers

        for provider in providers:
            try:
                response = provider["client"].chat.completions.create(
                    model=provider["model"],
                    messages=messages,
                    max_tokens=max_tokens,
                )
                text = response.choices[0].message.content
                if text:
                    logger.info(f"[{tier}] Response from {provider['name']}")
                    return text.strip()
            except Exception as e:
                logger.warning(f"{provider['name']} failed: {e}")
                continue

        logger.error("All AI providers failed.")
        return None


# Singleton
ai = AIProvider()
