"""Message router — classifies intent and picks the right model tier.

Uses the classifier to score message complexity:
- Casual chat ("hey", "lol", "thanks") → fast tier (Groq/Cerebras, free)
- Complex questions ("explain X", "write me Y") → smart tier (OpenRouter, paid)
"""

from __future__ import annotations

from anna.core.ai import ai
from anna.core.classifier import classify
from anna.core.config import logger
from anna.core.message import Message, Response
from anna.persona.prompts import get_system_prompt
from anna.memory.store import memory


def handle_message(msg: Message) -> Response | None:
    """Process an incoming DM and return a response."""

    if not msg.text.strip():
        return None

    if not ai.available:
        return Response(text="AI is not configured yet.", chat_id=msg.chat_id)

    # Classify message complexity and pick model tier
    tier = classify(msg.text)
    logger.info(f"[router] '{msg.text[:50]}...' → {tier} tier")

    # Build conversation messages
    history = memory.get_history(msg.chat_id, msg.user.id)
    messages = history + [{"role": "user", "content": msg.text}]

    system_prompt = get_system_prompt(
        user_name=msg.user.display_name or msg.user.username or "friend",
        is_owner=memory.is_owner(msg.user.id),
    )

    reply_text = ai.chat(messages, system_prompt=system_prompt, tier=tier)
    if not reply_text:
        return None

    # Save to history
    memory.add_to_history(msg.chat_id, msg.user.id, "user", msg.text)
    memory.add_to_history(msg.chat_id, msg.user.id, "assistant", reply_text)

    return Response(text=reply_text, chat_id=msg.chat_id)
