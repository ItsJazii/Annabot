"""Regression test for /learn and /unlearn commands.

Flow:
  1. /learn  a fact  →  Anna stores it
  2. Ask Anna about the topic  →  she recalls the fact
  3. /unlearn the topic  →  Anna forgets it
  4. Ask again  →  fact is gone
"""

import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: main.py blows up without BOT_TOKEN, so set minimal env vars
# and stub heavy imports before importing anything from main.
# ---------------------------------------------------------------------------
os.environ.setdefault("BOT_TOKEN", "fake-token-for-testing")
os.environ.setdefault("BOT_OWNER_ID", "6758092469")

# Prevent real Supabase / Groq / Cerebras connections
os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_KEY", None)
os.environ.pop("GROQ_API_KEY", None)
os.environ.pop("CEREBRAS_API_KEY", None)
os.environ.pop("OPENROUTER_API_KEY", None)

# Stub out the telegram Application.builder so the bot doesn't actually start
with patch("telegram.ext.Application"):
    import main  # noqa: E402 (import not at top-level by necessity)


OWNER_ID = 6758092469
NON_OWNER_ID = 1234567890


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(user_id: int, username: str = "testuser") -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.username = username
    user.first_name = username
    user.is_bot = False
    return user


def _make_update(user_id: int, text: str = "", args: list | None = None) -> tuple:
    """Return (update, context) mocks wired up like PTB dispatches them."""
    user = _make_user(user_id)
    update = MagicMock()
    update.effective_user = user
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.args = args or []
    return update, context


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_learned_facts(tmp_path):
    """Give each test a clean learned-facts dict and a temp file for saves."""
    original = main._learned_facts.copy()
    main._learned_facts.clear()

    tmp_db = str(tmp_path / "learned_db.json")
    original_db = main.LEARNED_DB
    main.LEARNED_DB = tmp_db

    yield

    main._learned_facts.clear()
    main._learned_facts.update(original)
    main.LEARNED_DB = original_db


# ---------------------------------------------------------------------------
# Unit tests – core functions
# ---------------------------------------------------------------------------

class TestCoreLearnedFacts:
    """Directly exercise add_learned_fact / forget_learned / find_relevant_learned."""

    def test_add_and_find(self):
        assert main.add_learned_fact("MegaETH", "MegaETH is a real-time L2 with sub-ms blocks")
        hits = main.find_relevant_learned("tell me about megaeth")
        assert len(hits) == 1
        assert hits[0][0] == "MegaETH"
        assert "real-time L2" in hits[0][1]

    def test_forget_removes_fact(self):
        main.add_learned_fact("MegaETH", "MegaETH is a real-time L2")
        assert main.forget_learned("MegaETH")
        assert main.find_relevant_learned("tell me about megaeth") == []

    def test_forget_nonexistent_returns_false(self):
        assert main.forget_learned("nonexistent topic") is False

    def test_add_empty_topic_fails(self):
        assert main.add_learned_fact("", "some fact") is False

    def test_add_empty_fact_fails(self):
        assert main.add_learned_fact("topic", "") is False

    def test_normalize_topic_is_case_insensitive(self):
        main.add_learned_fact("Bitcoin Price", "BTC is volatile")
        hits = main.find_relevant_learned("what is the bitcoin price today?")
        assert len(hits) >= 1
        assert main.forget_learned("BITCOIN PRICE")
        assert main.find_relevant_learned("bitcoin price") == []

    def test_hit_counter_increments(self):
        main.add_learned_fact("solana", "Solana is a fast L1 blockchain")
        main.find_relevant_learned("tell me about solana")
        key = main._normalize_topic("solana")
        assert main._learned_facts[key]["hits"] == 1
        main.find_relevant_learned("solana news")
        assert main._learned_facts[key]["hits"] == 2

    def test_fact_persists_to_json(self, tmp_path):
        main.add_learned_fact("persist test", "should be saved")
        with open(main.LEARNED_DB, "r") as f:
            data = json.load(f)
        key = main._normalize_topic("persist test")
        assert key in data
        assert data[key]["fact"] == "should be saved"


# ---------------------------------------------------------------------------
# Integration tests – command handlers
# ---------------------------------------------------------------------------

class TestLearnCommand:

    @pytest.mark.asyncio
    async def test_learn_stores_fact(self):
        update, ctx = _make_update(OWNER_ID, args=["megaeth", "chain", "|", "MegaETH", "is", "a", "real-time", "L2"])
        await main.learn_command(update, ctx)

        update.message.reply_text.assert_called_once()
        reply = update.message.reply_text.call_args[0][0]
        assert "Got it" in reply or "remember" in reply.lower()

        hits = main.find_relevant_learned("what is megaeth?")
        assert len(hits) >= 1
        assert "real-time L2" in hits[0][1]

    @pytest.mark.asyncio
    async def test_learn_rejects_non_owner(self):
        update, ctx = _make_update(NON_OWNER_ID, args=["topic", "|", "fact"])
        await main.learn_command(update, ctx)
        reply = update.message.reply_text.call_args[0][0]
        assert "master" in reply.lower()

    @pytest.mark.asyncio
    async def test_learn_rejects_missing_pipe(self):
        update, ctx = _make_update(OWNER_ID, args=["no", "pipe", "here"])
        await main.learn_command(update, ctx)
        reply = update.message.reply_text.call_args[0][0]
        assert "/learn" in reply


class TestUnlearnCommand:

    @pytest.mark.asyncio
    async def test_unlearn_removes_fact(self):
        main.add_learned_fact("megaeth chain", "MegaETH is a real-time L2")

        update, ctx = _make_update(OWNER_ID, args=["megaeth", "chain"])
        await main.unlearn_command(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        assert "Forgotten" in reply or "forgotten" in reply

        assert main.find_relevant_learned("megaeth") == []

    @pytest.mark.asyncio
    async def test_unlearn_nonexistent_topic(self):
        update, ctx = _make_update(OWNER_ID, args=["nonexistent"])
        await main.unlearn_command(update, ctx)
        reply = update.message.reply_text.call_args[0][0]
        assert "don't have" in reply.lower()

    @pytest.mark.asyncio
    async def test_unlearn_rejects_non_owner(self):
        update, ctx = _make_update(NON_OWNER_ID, args=["topic"])
        await main.unlearn_command(update, ctx)
        reply = update.message.reply_text.call_args[0][0]
        assert "master" in reply.lower()

    @pytest.mark.asyncio
    async def test_unlearn_no_args(self):
        update, ctx = _make_update(OWNER_ID, args=[])
        await main.unlearn_command(update, ctx)
        reply = update.message.reply_text.call_args[0][0]
        assert "/unlearn" in reply


# ---------------------------------------------------------------------------
# Full regression: learn → recall → unlearn → verify forgotten
# ---------------------------------------------------------------------------

class TestLearnUnlearnRegression:
    """End-to-end regression: the complete lifecycle of a learned fact."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        # Step 1: Learn a fact via /learn command
        learn_update, learn_ctx = _make_update(
            OWNER_ID,
            args=["quantum", "computing", "|", "Quantum", "computers", "use", "qubits", "not", "classical", "bits"],
        )
        await main.learn_command(learn_update, learn_ctx)
        learn_reply = learn_update.message.reply_text.call_args[0][0]
        assert "Got it" in learn_reply

        # Step 2: Verify Anna can recall the fact
        hits = main.find_relevant_learned("tell me about quantum computing")
        assert len(hits) >= 1, "Anna should recall the learned fact"
        assert "qubits" in hits[0][1], "Recalled fact should mention qubits"

        # Step 3: Unlearn the fact via /unlearn command
        unlearn_update, unlearn_ctx = _make_update(OWNER_ID, args=["quantum", "computing"])
        await main.unlearn_command(unlearn_update, unlearn_ctx)
        unlearn_reply = unlearn_update.message.reply_text.call_args[0][0]
        assert "Forgotten" in unlearn_reply or "forgotten" in unlearn_reply

        # Step 4: Verify Anna no longer recalls the fact
        hits_after = main.find_relevant_learned("tell me about quantum computing")
        assert hits_after == [], "Anna should NOT recall the unlearned fact"

    @pytest.mark.asyncio
    async def test_relearn_after_unlearn(self):
        """Ensure a topic can be re-learned after being unlearned."""
        main.add_learned_fact("dogecoin", "DOGE started as a joke coin")
        assert main.forget_learned("dogecoin")

        main.add_learned_fact("dogecoin", "DOGE is now accepted by Tesla")
        hits = main.find_relevant_learned("what is dogecoin?")
        assert len(hits) == 1
        assert "Tesla" in hits[0][1]
