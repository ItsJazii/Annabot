# Anna — Telegram AI Companion Bot

Anna is a cute anime-waifu Telegram bot with personality, real-time web search, vision, voice, group memory, translation, and admin tools. Built in Python with `python-telegram-bot`, multi-provider AI failover, and Supabase for persistent state.

Bot handle: **[@annatranlatorbot](https://t.me/annatranlatorbot)**
Repo: **[ItsJazii/Annabot](https://github.com/ItsJazii/Annabot)**

## What Anna does

**AI personality**
- Cute anime-waifu energy — soft, playful, warm, slightly flirty for everyone, full devoted-master mode for the verified owner.
- Wholesome SFW for everyone (owner included). No NSFW, no slurs, no hate speech.
- Forms opinions about people based on how they treat her, defends her friends, and remembers conversations across restarts.

**Real-time knowledge**
- Web search via Gemini Flash `:online` — auto-triggers on questions ("what is", "who is", trailing `?`, etc.) and grounds replies with live web results in a single round trip.
- Real-time crypto prices via CoinGecko (20+ coins) — bypasses the LLM for accuracy.

**Senses**
- **Vision** — sees photos when mentioned in a caption or replied to with a mention. Reacts naturally.
- **Voice** — transcribes voice notes via Groq Whisper (DM owner or reply-to-bot in groups) and replies as if it were text.

**Group features**
- Group context awareness — Anna sees the last few messages in the group, not just the one mentioning her.
- `/tldr` — LLM-generated TLDR of the last 6 hours of group chat.
- `/vibe` — one-line vibe check on the last hour ("chaotic gamer energy 🎮").
- Emoji reactions for short messages ("lol", "ty", "gn") instead of typing a reply.
- Anti-spam cooldown so spamming "anna anna anna" only gets one reply.

**Translation**
- Inline: `@annatranlatorbot <text>` from any chat.
- Reply-based: `/translate` on someone's message.
- Auto-translate: `/auto` enables it for a group, `/disableauto` turns it off.

**Moderation**
- Admin: `/mute`, `/unmute`, `/kick` (reply-based).
- Anna auto-mutes (via Telegram `restrict_chat_member`) after 3 strikes for severe explicit content. Mild/medium words just get a cute warning.
- Anti-manipulation: Anna ignores fake authority claims, refuses to harm herself, never uses slurs.

**Owner-only**
- `/image <prompt>` — Pollinations.ai image gen.
- `/video <query>` — DuckDuckGo video search.
- `/shutup` / `/speak` — global silence toggle (also natural language).
- `/memory` (reply) / `/forget` (reply) — inspect or wipe what Anna knows about someone.
- `/tldrdebug` — see the raw TLDR buffer.

## Architecture

- **Single-process Python** — `main.py` (handlers, db, memory, helpers) + `prompts.py` (personality blocks).
- **3-provider failover** for chat: OpenRouter Gemini 2.0 Flash (primary, paid, ~$0.075/1M tok) → Groq Llama 3.3 70B (free) → Cerebras Llama 3.1 8B (free).
- **Web search**: appends `:online` to the Gemini call, runs Exa search, $0.005/request.
- **Voice transcription**: Groq Whisper Large v3 Turbo (free tier).
- **Storage**: Supabase primary with atomic JSON fallback (`users_db.json`, `groups_db.json`, `admins_db.json`, `stickers.json`, `memory_db.json`, `history_db.json`).
- **Health check**: Flask + Waitress on `$PORT` (default 10000) so Render can ping it.

Handler order in PTB:
- `group=0` capture (TLDR buffer for all messages)
- `group=1` auto-translate
- `group=2` Anna chat (text), Anna vision (photos), Anna voice

## Setup

### Environment variables

| Key | Required | Description |
|-----|----------|-------------|
| `BOT_TOKEN` | Yes | From [@BotFather](https://t.me/BotFather) |
| `OPENROUTER_API_KEY` | Yes | From [openrouter.ai](https://openrouter.ai) — used for chat, search, vision |
| `OPENROUTER_MODEL` | Optional | OpenRouter model slug. Defaults to `google/gemini-2.5-flash` |
| `GROQ_API_KEY` | Yes | From [console.groq.com](https://console.groq.com) — fallback chat + voice transcription |
| `CEREBRAS_API_KEY` | Yes | From [cloud.cerebras.ai](https://cloud.cerebras.ai) — fallback chat |
| `BOT_OWNER_ID` | Yes | Your Telegram user ID |
| `SUPABASE_URL` | Optional | Supabase project URL |
| `SUPABASE_KEY` | Optional | Supabase anon key |
| `PORT` | Optional | Health check port (defaults to 10000) |

### Install & run

```bash
pip install -r requirements.txt
python main.py
```

### Telegram setup

1. Create the bot via [@BotFather](https://t.me/BotFather), grab the token.
2. Disable privacy mode: BotFather → `/setprivacy` → your bot → **Disable**. Without this, Anna can't read group messages, breaking TLDR + auto-translate + group context.
3. To enable real Telegram mute on strikes, give the bot **Restrict members** admin permission in your group.

### Deploy on Render

1. Connect the GitHub repo.
2. Set the env vars listed above.
3. Render auto-deploys on push to `main`. Free tier sleeps after 15min — use UptimeRobot to ping `/health` every 10min.

## Files

```
.
├── main.py              # Bot logic, handlers, db, memory, vision, voice
├── prompts.py           # Anna's personality (base + SFW + owner)
├── requirements.txt     # Python deps
├── render.yaml          # Render config
├── .env.example         # Env template
├── README.md            # This file
├── PROJECT_STATUS.md    # Internal status / changelog (gitignored)
├── memory_db.json       # User memory (auto-created)
├── history_db.json      # Conversation history (auto-created, persistent)
├── users_db.json        # Username→ID fallback
├── groups_db.json       # Group settings fallback
├── admins_db.json       # Admin list fallback
└── stickers.json        # Cached sticker IDs
```

## Notes

- All file writes are atomic (`tmp + os.replace`) to survive crashes / concurrent writes.
- Conversation history (`history_db.json`) is coalesced — saved every 30s instead of on every message.
- The bot exits with exponential backoff (10s → 5min) and `drop_pending_updates=True` to avoid Conflict errors on restart.
