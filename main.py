"""fin-invest: Investment monitoring daemon.

Entry point that starts Telegram bot, scheduler, and health monitor
in a single asyncio event loop.
"""

import asyncio
import logging
import logging.handlers
import signal
import sys

from config import LOG_DIR
from db import Database

# ─── Logging Setup ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.handlers.TimedRotatingFileHandler(
            LOG_DIR / "invest.log",
            when="midnight",
            backupCount=7,
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("invest")


async def main():
    logger.info("=" * 60)
    logger.info("fin-invest starting...")
    logger.info("=" * 60)

    # 1. Initialize DB
    db = Database()
    if not db.check_integrity():
        logger.error("DB integrity check failed! Exiting.")
        sys.exit(1)
    logger.info("DB initialized: %.1fMB, %s", db.db_size_mb(), db.table_counts())

    # 2. Initialize scheduler (collectors + jobs)
    from scheduler.jobs import CollectorManager
    collector_mgr = CollectorManager(db)
    collector_mgr.start()

    # 3. Shutdown handler
    shutdown_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    logger.info("fin-invest running. Press Ctrl+C to stop.")

    # 4. Wait for shutdown
    await shutdown_event.wait()

    # 5. Cleanup
    logger.info("Shutting down...")
    await collector_mgr.shutdown()
    logger.info("fin-invest stopped.")


if __name__ == "__main__":
    asyncio.run(main())
