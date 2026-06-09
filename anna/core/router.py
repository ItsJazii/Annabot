"""Message router — decides how to handle incoming messages.

For now this is a simple pass-through to the AI chat. As features are added
(web search, image gen, tools, etc.), the router will classify intent and
dispatch to the right handler.
"""

from __future__ import annotations

from anna.core.ai import ai
from anna.core.config import logger
from anna.core.message import Message, Response
from anna.persona.prompts import get_system_prompt
from anna.memory.store import memory


def handle_message(msg: Message) -> Response | None:
    """Process an incoming message and return a response (or None to stay silent)."""

    # In groups, only respond if mentioned or replied to
    if not msg.is_private and not msg.mentions_bot and not msg.reply_to_bot:
        return None

    if not msg.text.strip():
        return None

    if not ai.available:
        return Response(text="AI is not configured yet.", chat_id=msg.chat_id)

    # Build conversation messages
    history = memory.get_history(msg.chat_id, msg.user.id)
    messages = history + [{"role": "user", "content": msg.text}]

    system_prompt = get_system_prompt(
        user_name=msg.user.display_name or msg.user.username or "friend",
        is_owner=False,  # TODO: wire up owner check
    )

    reply_text = ai.chat(messages, system_prompt=system_prompt)
    if not reply_text:
        return None

    # Save to history
    memory.add_to_history(msg.chat_id, msg.user.id, "user", msg.text)
    memory.add_to_history(msg.chat_id, msg.user.id, "assistant", reply_text)

    return Response(text=reply_text, chat_id=msg.chat_id)
