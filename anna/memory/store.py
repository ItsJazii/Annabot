"""Persistent memory — Supabase with local JSON fallback.

Handles:
- Conversation history (per chat + user)
- User tracking
- Admin/owner data
"""

from __future__ import annotations

import json
import os
from typing import Optional

from anna.core.config import SUPABASE_URL, SUPABASE_KEY, logger

# Supabase client (optional)
_supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client

        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase connected successfully!")
    except Exception as e:
        logger.error(f"Supabase connection failed: {e}")
else:
    logger.warning("Supabase credentials not found. Using local JSON fallback.")


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------
HISTORY_FILE = "history_db.json"
USERS_FILE = "users_db.json"
ADMINS_FILE = "admins_db.json"


def _load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def _save_json(path: str, data):
    try:
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception as e:
        logger.error(f"Failed to save {path}: {e}")


# ---------------------------------------------------------------------------
# Memory store
# ---------------------------------------------------------------------------
MAX_HISTORY = 20  # messages per conversation key


class MemoryStore:
    """Conversation history and user data, backed by Supabase or local JSON."""

    def __init__(self):
        self._history: dict[str, list[dict]] = _load_json(HISTORY_FILE, {})
        self._users: dict = {}
        self._admins: dict = {"owner_id": None, "admins": []}
        self._load_users()

    # -- User data ----------------------------------------------------------

    def _load_users(self):
        if _supabase:
            try:
                result = _supabase.table("users").select("*").execute()
                self._users = {row["username"]: str(row["user_id"]) for row in result.data}

                result = _supabase.table("admins").select("*").execute()
                if result.data:
                    self._admins = {
                        "owner_id": result.data[0].get("owner_id"),
                        "admins": result.data[0].get("admin_ids", []),
                    }
                logger.info("User data loaded from Supabase.")
                return
            except Exception as e:
                logger.error(f"Supabase user load failed: {e}")

        self._users = _load_json(USERS_FILE, {})
        self._admins = _load_json(ADMINS_FILE, {"owner_id": None, "admins": []})

    def track_user(self, username: Optional[str], user_id: str):
        if not username:
            return
        self._users[username] = str(user_id)
        if _supabase:
            try:
                _supabase.table("users").upsert(
                    {"username": username, "user_id": user_id},
                    on_conflict="username",
                ).execute()
                return
            except Exception as e:
                logger.error(f"Supabase track user failed: {e}")
        _save_json(USERS_FILE, self._users)

    def get_owner_id(self) -> Optional[str]:
        owner = self._admins.get("owner_id")
        if owner:
            return str(owner)
        from anna.core.config import BOT_OWNER_ID
        return str(BOT_OWNER_ID) if BOT_OWNER_ID else None

    def is_owner(self, user_id: str) -> bool:
        owner = self.get_owner_id()
        return owner is not None and str(user_id) == owner

    # -- Conversation history -----------------------------------------------

    def _history_key(self, chat_id: str, user_id: str) -> str:
        return f"{chat_id}:{user_id}"

    def get_history(self, chat_id: str, user_id: str) -> list[dict]:
        key = self._history_key(chat_id, user_id)
        return list(self._history.get(key, []))

    def add_to_history(self, chat_id: str, user_id: str, role: str, content: str):
        key = self._history_key(chat_id, user_id)
        if key not in self._history:
            self._history[key] = []
        self._history[key].append({"role": role, "content": content})
        # Trim to last N messages
        if len(self._history[key]) > MAX_HISTORY:
            self._history[key] = self._history[key][-MAX_HISTORY:]
        _save_json(HISTORY_FILE, self._history)

    def clear_history(self, chat_id: str, user_id: str):
        key = self._history_key(chat_id, user_id)
        self._history.pop(key, None)
        _save_json(HISTORY_FILE, self._history)


# Singleton
memory = MemoryStore()
