"""Anna — entry point.

Starts the health server and the Telegram bot (more platforms coming).
"""

import time
import threading

from anna.core.config import logger
from anna.health import run_health_server
from anna.platforms.telegram import create_telegram_app


def run_bot():
    backoff = 10
    max_backoff = 300

    while True:
        try:
            app = create_telegram_app()
            logger.info("Bot is running...")
            app.run_polling(drop_pending_updates=True)
            backoff = 10
        except Exception as e:
            logger.error(f"Bot crashed: {e}")

        logger.info(f"Restarting in {backoff} seconds...")
        time.sleep(backoff)
        backoff = min(backoff * 2, max_backoff)


def main():
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    logger.info("Health endpoint started")

    run_bot()


if __name__ == "__main__":
    main()
