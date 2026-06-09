# Anna — Personal AI Assistant

Anna is a private, DM-only AI assistant built in Python. She talks to you directly across messaging platforms, starting with Telegram. Built with a modular architecture so adding Discord, WhatsApp, and more is just a new connector file.

Bot handle: **[@annatranlatorbot](https://t.me/annatranlatorbot)**

## Architecture

```
anna/
├── core/
│   ├── config.py      # All env vars and settings
│   ├── ai.py          # AI providers with failover (OpenRouter → Groq → Cerebras)
│   ├── message.py     # Platform-agnostic Message/Response/User models
│   └── router.py      # Message routing and intent dispatch
├── memory/
│   └── store.py       # Supabase + local JSON fallback
├── persona/
│   └── prompts.py     # Personality (XML-structured, modular sections)
├── platforms/
│   └── telegram.py    # Telegram DM connector
└── health.py          # Flask health endpoints for Render
main.py                # Entry point
```

- **Platform-agnostic core**: every platform normalizes messages into a `Message` dataclass. The router and AI never touch platform specifics.
- **Pluggable connectors**: adding a new platform = one new file in `anna/platforms/`.
- **AI failover**: OpenRouter (primary) → Groq (fallback) → Cerebras (fallback).
- **Memory**: Supabase with automatic local JSON fallback.

## Setup

### Environment variables

| Key | Required | Description |
|-----|----------|-------------|
| `BOT_TOKEN` | Yes | Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `OPENROUTER_API_KEY` | Yes | From [openrouter.ai](https://openrouter.ai) |
| `OPENROUTER_MODEL` | Optional | Model slug (default: `google/gemini-2.5-flash`) |
| `GROQ_API_KEY` | Yes | From [console.groq.com](https://console.groq.com) |
| `CEREBRAS_API_KEY` | Yes | From [cloud.cerebras.ai](https://cloud.cerebras.ai) |
| `BOT_OWNER_ID` | Yes | Your Telegram user ID |
| `SUPABASE_URL` | Optional | Supabase project URL |
| `SUPABASE_KEY` | Optional | Supabase anon key |
| `PORT` | Optional | Health check port (default: 10000) |

### Install and run

```bash
pip install -r requirements.txt
python main.py
```

### Deploy on Render

1. Connect this GitHub repo to a new Render web service.
2. Build command: `pip install -r requirements.txt`
3. Start command: `python main.py`
4. Set the env vars listed above.
5. Use UptimeRobot to ping `/health` every 5 minutes to prevent free tier sleep.

## Notes

- Anna only responds in private DMs. She ignores group chats.
- Maintenance mode: set `MAINTENANCE_MODE = True` in `anna/core/config.py` to have Anna auto-reply that she's under construction.
- All secrets stay in environment variables. Nothing private is ever committed to git.
