"""Centralized configuration — all env vars and settings live here."""

import os
import logging

from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_OWNER_ID = os.getenv("BOT_OWNER_ID")

# Server
PORT = int(os.getenv("PORT", 10000))

# AI Providers
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")

# Optional
CMC_API_KEY = os.getenv("CMC_API_KEY")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Maintenance mode — flip to False when the rebuild is live
MAINTENANCE_MODE = True

MAINTENANCE_MESSAGE = (
    "\U0001f6a7 Hey! Anna is currently under construction and getting a HUGE update! \U0001f6a7\n\n"
    "All commands and features are temporarily disabled.\n"
    "Try again later \u2014 I'll be back better than ever! \U0001f496"
)

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("anna")
