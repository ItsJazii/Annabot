"""Message router — classifies intent and picks the right model tier.

Uses the classifier to score message complexity:
- Casual chat ("hey", "lol", "thanks") → fast tier (Groq/Cerebras, free)
- Complex questions ("explain X", "write me Y") → smart tier (OpenRouter, paid)

Also handles memory, web search, and summarization.
"""

from __future__ import annotations

from anna.core.ai import ai
from anna.core.classifier import classify
from anna.core.config import logger
from anna.core.message import Message, Response
from anna.persona.prompts import get_system_prompt
from anna.memory.store import memory
from anna.memory.summarizer import summarize_conversation, extract_user_facts
from anna.tools.search import needs_search, search


def handle_message(msg: Message) -> Response | None:
    """Process an incoming DM and return a response."""

    if not msg.text.strip():
        return None

    if not ai.available:
        return Response(text="AI is not configured yet.", chat_id=msg.chat_id)

    # Classify message complexity and pick model tier
    tier = classify(msg.text)
    logger.info(f"[router] '{msg.text[:50]}...' → {tier} tier")

    # Check if this message needs a web search
    search_context = ""
    if needs_search(msg.text):
        logger.info(f"[search] Searching for: {msg.text[:50]}")
        search_context = search(msg.text)
        if search_context:
            logger.info(f"[search] Got results ({len(search_context)} chars)")
            # Bump to smart tier for search queries so Anna processes results well
            tier = "smart"

    # Build memory context
    memory_context = memory.build_context(msg.chat_id, msg.user.id)

    # Build conversation messages (recent history + current message)
    history = memory.get_history(msg.chat_id, msg.user.id)

    # If we have search results, inject them into the user message
    if search_context:
        augmented_text = (
            f"{msg.text}\n\n"
            f"[search results for context, use naturally in your response:\n"
            f"{search_context}]"
        )
        messages = history + [{"role": "user", "content": augmented_text}]
    else:
        messages = history + [{"role": "user", "content": msg.text}]

    system_prompt = get_system_prompt(
        user_name=msg.user.display_name or msg.user.username or "friend",
        is_owner=memory.is_owner(msg.user.id),
        memory_context=memory_context,
    )

    reply_text = ai.chat(messages, system_prompt=system_prompt, tier=tier)
    if not reply_text:
        return None

    # Save to history (save original text, not augmented)
    memory.add_to_history(msg.chat_id, msg.user.id, "user", msg.text)
    memory.add_to_history(msg.chat_id, msg.user.id, "assistant", reply_text)

    # Check if we need to summarize and extract facts (best effort)
    _maybe_update_memory(msg)

    return Response(text=reply_text, chat_id=msg.chat_id)


def _maybe_update_memory(msg: Message):
    """Trigger summarization and fact extraction if enough messages accumulated."""
    try:
        if memory.needs_summary(msg.chat_id, msg.user.id):
            logger.info(f"[memory] Triggering summarization for user {msg.user.id}")

            # Get all messages for summarization
            full_history = memory.get_full_history(msg.chat_id, msg.user.id)
            existing_summary = memory.get_summary(msg.chat_id, msg.user.id)

            # Summarize
            new_summary = summarize_conversation(ai, existing_summary, full_history)
            if new_summary:
                memory.save_summary(msg.chat_id, msg.user.id, new_summary)

            # Extract facts from recent messages
            recent = full_history[-20:]
            facts = extract_user_facts(ai, recent)
            for key, value in facts.items():
                memory.save_user_fact(msg.user.id, key, value)

            # Trim local history after summarization
            memory.trim_history_after_summary(msg.chat_id, msg.user.id)

            logger.info(f"[memory] Summary updated, {len(facts)} facts extracted")
    except Exception as e:
        logger.error(f"[memory] Update failed (non-fatal): {e}")
