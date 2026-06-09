"""Telegram platform connector.

Translates between Telegram's API and Anna's platform-agnostic Message model.
"""

from __future__ import annotations

import asyncio
import re

from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import (
    Application,
    CommandHandler,
    InlineQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from anna.core.config import BOT_TOKEN, MAINTENANCE_MODE, MAINTENANCE_MESSAGE, logger
from anna.core.message import Message, User
from anna.core.router import handle_message
from anna.memory.store import memory


def _normalize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Message | None:
    """Convert a Telegram Update into a normalized Message."""
    msg = update.message
    if not msg:
        return None

    user = msg.from_user
    if not user:
        return None
    text = msg.text or ""
    bot_username = context.bot_data.get("username", "anna")

    is_command = text.startswith("/")
    command = text.split()[0][1:].split("@")[0].lower() if is_command else None

    text_lower = text.lower()
    is_mentioned = (
        bool(re.search(r"\banna\b", text_lower))
        or f"@{bot_username}" in text_lower
    )

    is_reply = (
        msg.reply_to_message is not None
        and msg.reply_to_message.from_user is not None
        and msg.reply_to_message.from_user.id == context.bot.id
    )

    return Message(
        platform="telegram",
        chat_id=str(msg.chat_id),
        user=User(
            id=str(user.id),
            username=user.username,
            display_name=user.first_name,
        ),
        text=text,
        is_private=msg.chat.type == "private",
        is_command=is_command,
        command=command,
        reply_to_bot=is_reply,
        mentions_bot=is_mentioned,
        raw=update,
    )


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def _on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all non-command text messages."""
    msg = _normalize(update, context)
    if not msg:
        return

    # Track user
    memory.track_user(msg.user.username, msg.user.id)

    response = await asyncio.to_thread(handle_message, msg)
    if response and update.message:
        await update.message.reply_text(response.text)


async def _on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle slash commands — placeholder for future commands."""
    msg = _normalize(update, context)
    if not msg or not update.message:
        return

    # For now, treat commands like normal messages routed through the AI
    memory.track_user(msg.user.username, msg.user.id)

    response = await asyncio.to_thread(handle_message, msg)
    if response:
        await update.message.reply_text(response.text)


# ---------------------------------------------------------------------------
# Maintenance mode handlers
# ---------------------------------------------------------------------------

async def _maintenance_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(MAINTENANCE_MESSAGE)


async def _maintenance_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.inline_query:
        await update.inline_query.answer(
            [InlineQueryResultArticle(
                id="maintenance",
                title="\U0001f6a7 Anna is under construction!",
                input_message_content=InputTextMessageContent(MAINTENANCE_MESSAGE),
            )],
            cache_time=5,
        )


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

async def _post_init(application: Application):
    """Store bot username after startup."""
    bot = await application.bot.get_me()
    application.bot_data["username"] = bot.username.lower() if bot.username else "anna"
    logger.info(f"Telegram bot @{application.bot_data['username']} ready")


def create_telegram_app() -> Application:
    """Build and configure the Telegram Application."""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is missing! Set it in environment variables.")

    application = Application.builder().token(BOT_TOKEN).build()
    application.post_init = _post_init

    if MAINTENANCE_MODE:
        application.add_handler(CommandHandler("start", _maintenance_reply))
        application.add_handler(MessageHandler(filters.ChatType.PRIVATE, _maintenance_reply))
        application.add_handler(InlineQueryHandler(_maintenance_inline))
        logger.info("\U0001f6a7 MAINTENANCE MODE is ON")
    else:
        # Normal operation
        application.add_handler(CommandHandler("start", _on_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_message))

    return application
