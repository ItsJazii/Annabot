import json
import logging
import os
import time
import threading

from dotenv import load_dotenv
from flask import Flask
from supabase import create_client, Client
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, InlineQueryHandler, MessageHandler, filters, ContextTypes
from groq import Groq
import requests

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))
OWNER_ENV = os.getenv("BOT_OWNER_ID")

# =========================
# MAINTENANCE MODE
# =========================
# Set to True to disable all commands and auto-reply with an "under construction" notice.
# Flip back to False when the update is done.
MAINTENANCE_MODE = True

MAINTENANCE_MESSAGE = (
    "\U0001f6a7 Hey! Anna is currently under construction and getting a HUGE update! \U0001f6a7\n\n"
    "All commands and features are temporarily disabled.\n"
    "Try again later \u2014 I'll be back better than ever! \U0001f496"
)

# Supabase config
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
CMC_API_KEY = os.getenv("CMC_API_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing! Set it in Render Environment Variables.")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# =========================
# AI PROVIDER SETUP
# =========================
gemini_model = None
groq_client = None
cerebras_client = None

if GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
        gemini_model = True
        logger.info("Groq AI connected as fallback #1")
    except Exception as e:
        logger.error(f"Groq setup failed: {e}")

if CEREBRAS_API_KEY:
    try:
        from openai import OpenAI as CerebrasClient
        cerebras_client = CerebrasClient(
            api_key=CEREBRAS_API_KEY,
            base_url="https://api.cerebras.ai/v1"
        )
        if not gemini_model:
            gemini_model = True
        logger.info("Cerebras AI connected as fallback #2")
    except Exception as e:
        logger.error(f"Cerebras setup failed: {e}")

openrouter_client = None
if OPENROUTER_API_KEY:
    try:
        from openai import OpenAI as OpenRouterClient
        import httpx
        transport = httpx.HTTPTransport(retries=1)
        http_client = httpx.Client(transport=transport, timeout=10.0)
        openrouter_client = OpenRouterClient(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            http_client=http_client
        )
        if not gemini_model:
            gemini_model = True
        logger.info("OpenRouter AI connected as PRIMARY")
    except Exception as e:
        logger.error(f"OpenRouter setup failed: {e}")

if not gemini_model:
    logger.warning("No AI provider configured.")

# =========================
# FLASK HEALTH CHECK
# =========================
app = Flask(__name__)


@app.route("/")
def health():
    return "Bot is running!"


@app.route("/health")
def health_check():
    return {"status": "ok"}


def run_flask():
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=PORT)
    except ImportError:
        app.run(host="0.0.0.0", port=PORT)


# =========================
# SUPABASE SETUP
# =========================
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase connected successfully!")
    except Exception as e:
        logger.error(f"Supabase connection failed: {e}")
        supabase = None
else:
    logger.warning("Supabase credentials not found.")


# =========================
# LOCAL JSON HELPERS
# =========================
USERS_DB = "users_db.json"
GROUPS_DB = "groups_db.json"
ADMINS_DB = "admins_db.json"


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def save_json(path, data):
    try:
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception as e:
        logger.error(f"Failed to save {path}: {e}")


# =========================
# DATABASE
# =========================
class Database:
    def __init__(self):
        self.users = {}
        self.groups = {}
        self.admins = {"owner_id": None, "admins": []}
        self._load_all()

    def _load_all(self):
        if supabase:
            try:
                result = supabase.table("users").select("*").execute()
                self.users = {row["username"]: str(row["user_id"]) for row in result.data}

                result = supabase.table("groups").select("*").execute()
                self.groups = {str(row["chat_id"]): {"auto_translate": row["auto_translate"]} for row in result.data}

                result = supabase.table("admins").select("*").execute()
                if result.data:
                    self.admins = {
                        "owner_id": result.data[0].get("owner_id"),
                        "admins": result.data[0].get("admin_ids", [])
                    }

                logger.info("Data loaded from Supabase!")
                return
            except Exception as e:
                logger.error(f"Supabase load failed: {e}. Using JSON fallback.")

        self.users = load_json(USERS_DB, {})
        self.groups = load_json(GROUPS_DB, {})
        self.admins = load_json(ADMINS_DB, {"owner_id": None, "admins": []})

    def save_user(self, username, user_id):
        if supabase:
            try:
                supabase.table("users").upsert(
                    {"username": username, "user_id": user_id},
                    on_conflict="username"
                ).execute()
                return
            except Exception as e:
                logger.error(f"Supabase save user failed: {e}")
        save_json(USERS_DB, self.users)

    def save_groups(self):
        if supabase:
            try:
                for chat_id, data in self.groups.items():
                    supabase.table("groups").upsert(
                        {"chat_id": str(chat_id), "auto_translate": data.get("auto_translate", False)},
                        on_conflict="chat_id"
                    ).execute()
                return
            except Exception as e:
                logger.error(f"Supabase save groups failed: {e}")
        save_json(GROUPS_DB, self.groups)

    def save_admins(self):
        if supabase:
            try:
                supabase.table("admins").upsert({
                    "id": 1,
                    "owner_id": self.admins.get("owner_id"),
                    "admin_ids": self.admins.get("admins", [])
                }, on_conflict="id").execute()
                return
            except Exception as e:
                logger.error(f"Supabase save admins failed: {e}")
        save_json(ADMINS_DB, self.admins)


db = Database()


def get_owner_id():
    if db.admins.get("owner_id"):
        return str(db.admins["owner_id"])
    if OWNER_ENV:
        return str(OWNER_ENV)
    return None


def is_owner(user_id):
    owner = get_owner_id()
    return owner and str(user_id) == owner


def is_admin(user_id):
    return str(user_id) in [str(a) for a in db.admins.get("admins", [])]


# =========================
# BOT
# =========================
def run_bot():
    backoff = 10
    max_backoff = 300

    while True:
        try:
            application = Application.builder().token(BOT_TOKEN).build()

            # --- Maintenance mode gate ---
            if MAINTENANCE_MODE:
                async def maintenance_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
                    if update.message:
                        await update.message.reply_text(MAINTENANCE_MESSAGE)
                    elif update.callback_query:
                        await update.callback_query.answer(MAINTENANCE_MESSAGE, show_alert=True)

                async def maintenance_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
                    if update.inline_query:
                        await update.inline_query.answer(
                            [InlineQueryResultArticle(
                                id="maintenance",
                                title="\U0001f6a7 Bot is under construction!",
                                input_message_content=InputTextMessageContent(MAINTENANCE_MESSAGE),
                            )],
                            cache_time=5,
                        )

                application.add_handler(CommandHandler("start", maintenance_reply))
                application.add_handler(MessageHandler(filters.ChatType.PRIVATE, maintenance_reply))
                application.add_handler(InlineQueryHandler(maintenance_inline))

                logger.info("\U0001f6a7 MAINTENANCE MODE is ON \u2014 all handlers bypassed.")
                application.run_polling(drop_pending_updates=True)
                backoff = 10
                continue

            # TODO: Add new command and message handlers here after the rebuild

            logger.info("Bot is running...")
            application.run_polling(drop_pending_updates=True)
            backoff = 10

        except Exception as e:
            logger.error(f"Bot crashed: {e}")

        logger.info(f"Restarting in {backoff} seconds...")
        time.sleep(backoff)
        backoff = min(backoff * 2, max_backoff)


def main():
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"Health endpoint started on port {PORT}")

    run_bot()


if __name__ == "__main__":
    main()
