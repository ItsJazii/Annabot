"""Persistent memory — Supabase with local JSON fallback.

Handles:
- Full conversation history (stored forever in Supabase, trimmed locally)
- Per-user facts/memory (key things Anna learns about users)
- Conversation summaries (rolling summaries of old conversations)
- User tracking
- Admin/owner data
"""

from __future__ import annotations

import json
import os
import time
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
MEMORY_FILE = "memory_db.json"
SUMMARY_FILE = "summary_db.json"


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
RECENT_HISTORY_LIMIT = 30  # recent messages loaded into context
SUMMARY_TRIGGER = 40  # summarize after this many messages


class MemoryStore:
    """Conversation history, user facts, and summaries.

    Backed by Supabase or local JSON.
    """

    def __init__(self):
        self._history: dict[str, list[dict]] = _load_json(HISTORY_FILE, {})
        self._user_facts: dict[str, dict] = _load_json(MEMORY_FILE, {})
        self._summaries: dict[str, str] = _load_json(SUMMARY_FILE, {})
        self._users: dict = {}
        self._admins: dict = {"owner_id": None, "admins": []}
        self._load_users()
        self._load_facts_from_supabase()
        self._load_summaries_from_supabase()

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
        """Get recent conversation history for context window.

        Returns only role + content (strips metadata like timestamps)
        so it's ready to pass directly to the AI.
        """
        key = self._history_key(chat_id, user_id)
        messages = self._history.get(key, [])
        recent = messages[-RECENT_HISTORY_LIMIT:]
        return [{"role": m["role"], "content": m["content"]} for m in recent]

    def get_full_history(self, chat_id: str, user_id: str) -> list[dict]:
        """Get ALL messages for summarization."""
        key = self._history_key(chat_id, user_id)
        return list(self._history.get(key, []))

    def get_message_count(self, chat_id: str, user_id: str) -> int:
        """Get total number of messages in history."""
        key = self._history_key(chat_id, user_id)
        return len(self._history.get(key, []))

    def add_to_history(self, chat_id: str, user_id: str, role: str, content: str):
        key = self._history_key(chat_id, user_id)
        if key not in self._history:
            self._history[key] = []

        entry = {
            "role": role,
            "content": content,
            "timestamp": int(time.time()),
        }
        self._history[key].append(entry)

        # Store full history in Supabase
        if _supabase:
            try:
                _supabase.table("messages").upsert({
                    "chat_id": str(chat_id),
                    "user_id": str(user_id),
                    "role": role,
                    "content": content,
                    "timestamp": int(time.time()),
                }).execute()
            except Exception as e:
                logger.error(f"Supabase message save failed: {e}")

        _save_json(HISTORY_FILE, self._history)

    def trim_history_after_summary(self, chat_id: str, user_id: str):
        """After summarization, keep only recent messages locally."""
        key = self._history_key(chat_id, user_id)
        if key in self._history:
            self._history[key] = self._history[key][-RECENT_HISTORY_LIMIT:]
            _save_json(HISTORY_FILE, self._history)

    def needs_summary(self, chat_id: str, user_id: str) -> bool:
        """Check if conversation has enough messages to trigger a summary."""
        return self.get_message_count(chat_id, user_id) >= SUMMARY_TRIGGER

    def clear_history(self, chat_id: str, user_id: str):
        key = self._history_key(chat_id, user_id)
        self._history.pop(key, None)
        _save_json(HISTORY_FILE, self._history)

    # -- User facts (long-term memory) --------------------------------------

    def _load_facts_from_supabase(self):
        if _supabase:
            try:
                result = _supabase.table("user_facts").select("*").execute()
                for row in result.data:
                    uid = str(row["user_id"])
                    if uid not in self._user_facts:
                        self._user_facts[uid] = {}
                    self._user_facts[uid][row["fact_key"]] = row["fact_value"]
                logger.info(f"Loaded facts for {len(self._user_facts)} users from Supabase.")
            except Exception as e:
                logger.warning(f"Supabase facts load failed (table may not exist yet): {e}")

    def get_user_facts(self, user_id: str) -> dict:
        """Get all known facts about a user."""
        return dict(self._user_facts.get(str(user_id), {}))

    def get_user_facts_text(self, user_id: str) -> str:
        """Get user facts as a readable string for the system prompt."""
        facts = self.get_user_facts(user_id)
        if not facts:
            return ""
        lines = [f"- {k}: {v}" for k, v in facts.items()]
        return "\n".join(lines)

    def save_user_fact(self, user_id: str, key: str, value: str):
        """Save a fact about a user (overwrites existing)."""
        uid = str(user_id)
        if uid not in self._user_facts:
            self._user_facts[uid] = {}
        self._user_facts[uid][key] = value

        if _supabase:
            try:
                _supabase.table("user_facts").upsert({
                    "user_id": uid,
                    "fact_key": key,
                    "fact_value": value,
                    "updated_at": int(time.time()),
                }).execute()
            except Exception as e:
                logger.error(f"Supabase fact save failed: {e}")

        _save_json(MEMORY_FILE, self._user_facts)

    # -- Conversation summaries ---------------------------------------------

    def _load_summaries_from_supabase(self):
        if _supabase:
            try:
                result = _supabase.table("conversation_summaries").select("*").execute()
                for row in result.data:
                    key = f"{row['chat_id']}:{row['user_id']}"
                    self._summaries[key] = row["summary"]
                logger.info(f"Loaded {len(self._summaries)} conversation summaries from Supabase.")
            except Exception as e:
                logger.warning(f"Supabase summaries load failed (table may not exist yet): {e}")

    def get_summary(self, chat_id: str, user_id: str) -> str:
        """Get the conversation summary for a user."""
        key = self._history_key(chat_id, user_id)
        return self._summaries.get(key, "")

    def save_summary(self, chat_id: str, user_id: str, summary: str):
        """Save a conversation summary."""
        key = self._history_key(chat_id, user_id)
        self._summaries[key] = summary

        if _supabase:
            try:
                _supabase.table("conversation_summaries").upsert({
                    "chat_id": str(chat_id),
                    "user_id": str(user_id),
                    "summary": summary,
                    "updated_at": int(time.time()),
                }).execute()
            except Exception as e:
                logger.error(f"Supabase summary save failed: {e}")

        _save_json(SUMMARY_FILE, self._summaries)

    # -- Build full context for AI ------------------------------------------

    def build_context(self, chat_id: str, user_id: str) -> str:
        """Build the full memory context string to inject into system prompt.

        Returns a <context> block with user facts and conversation summary.
        """
        parts = []

        # User facts
        facts_text = self.get_user_facts_text(user_id)
        if facts_text:
            parts.append(f"Known facts about this user:\n{facts_text}")

        # Conversation summary
        summary = self.get_summary(chat_id, user_id)
        if summary:
            parts.append(f"Summary of previous conversations:\n{summary}")

        return "\n\n".join(parts)


# Singleton
memory = MemoryStore()
