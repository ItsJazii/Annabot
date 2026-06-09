"""Platform-agnostic message model.

Every platform connector normalizes incoming data into a Message object.
The core logic never touches Telegram/Discord/WhatsApp specifics directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class User:
    """Normalized user identity."""
    id: str
    username: Optional[str] = None
    display_name: Optional[str] = None


@dataclass
class Message:
    """A single incoming DM from any platform."""
    platform: str                       # "telegram", "discord", "whatsapp", etc.
    chat_id: str                        # Unique chat/conversation identifier
    user: User                          # Who sent it
    text: str = ""                      # Message body
    is_command: bool = False            # Starts with / or similar
    command: Optional[str] = None       # e.g. "start", "help" (without /)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw: object = None                  # Original platform-specific object for passthrough


@dataclass
class Response:
    """Anna's response, ready to be sent back through the platform connector."""
    text: str
    chat_id: str
    reply_to_message_id: Optional[str] = None
