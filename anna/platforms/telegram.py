"""Telegram platform connector.

Normalizes Telegram DMs into Anna's platform-agnostic Message model.
Anna only responds in private (DM) chats.
"""

from __future__ import annotations

import asyncio

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from anna.core.config import BOT_TOKEN, MAINTENANCE_MODE, MAINTENANCE_MESSAGE, logger
from anna.core.message import Message, User
from anna.core.router import handle_message
from anna.memory.store import memory


def _normalize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Message | None:
    """Convert a Telegram DM Update into a normalized Message."""
    msg = update.message
    if not msg:
        return None

    user = msg.from_user
    if not user:
        return None

    text = msg.text or ""

    is_command = text.startswith("/")
    command = text.split()[0][1:].split("@")[0].lower() if is_command else None

    return Message(
        platform="telegram",
        chat_id=str(msg.chat_id),
        user=User(
            id=str(user.id),
            username=user.username,
            display_name=user.first_name,
        ),
        text=text,
        is_command=is_command,
        command=command,
        raw=update,
    )


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def _on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all non-command text DMs."""
    msg = _normalize(update, context)
    if not msg:
        return

    memory.track_user(msg.user.username, msg.user.id)

    response = await asyncio.to_thread(handle_message, msg)
    if response and update.message:
        await update.message.reply_text(response.text)


async def _on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle slash commands in DMs."""
    msg = _normalize(update, context)
    if not msg or not update.message:
        return

    memory.track_user(msg.user.username, msg.user.id)

    response = await asyncio.to_thread(handle_message, msg)
    if response:
        await update.message.reply_text(response.text)


# ---------------------------------------------------------------------------
# Maintenance mode handler
# ---------------------------------------------------------------------------

async def _maintenance_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(MAINTENANCE_MESSAGE)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

async def _post_init(application: Application):
    """Store bot username after startup."""
    bot = await application.bot.get_me()
    application.bot_data["username"] = bot.username.lower() if bot.username else "anna"
    logger.info(f"Telegram bot @{application.bot_data['username']} ready")


def create_telegram_app() -> Application:
    """Build and configure the Telegram Application. DM-only."""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is missing! Set it in environment variables.")

    application = Application.builder().token(BOT_TOKEN).build()
    application.post_init = _post_init

    if MAINTENANCE_MODE:
        application.add_handler(
            MessageHandler(filters.ChatType.PRIVATE, _maintenance_reply)
        )
        logger.info("\U0001f6a7 MAINTENANCE MODE is ON")
    else:
        # DM-only handlers
        application.add_handler(
            CommandHandler("start", _on_command, filters=filters.ChatType.PRIVATE)
        )
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, _on_message)
        )

    return application
