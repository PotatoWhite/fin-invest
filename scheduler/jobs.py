"""APScheduler job definitions for data collection and maintenance."""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import (
    POLLING_INTERVAL_SEC, MARKET_DATA_INTERVAL_SEC,
    DAILY_COLLECT_HOUR, DB_BACKUP_HOUR, DB_COMPRESS_MINUTES_AFTER,
    HEALTH_CHECK_INTERVAL_SEC, KR_MARKET_OPEN, KR_MARKET_CLOSE,
)
from db import Database
from collectors.naver_stock import (
    NaverStockPollingCollector,
    NaverStockIntegrationCollector,
    NaverStockChartCollector,
)
from collectors.naver_index import (
    NaverKRIndexCollector,
    NaverForeignIndexCollector,
)
from collectors.naver_market import (
    NaverFXCollector,
    NaverCommodityCollector,
    NaverBondCollector,
    NaverCryptoCollector,
)

logger = logging.getLogger(__name__)


def is_kr_market_hours() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:  # Saturday, Sunday
        return False
    h, m = now.hour, now.minute
    open_min = KR_MARKET_OPEN[0] * 60 + KR_MARKET_OPEN[1]
    close_min = KR_MARKET_CLOSE[0] * 60 + KR_MARKET_CLOSE[1]
    current_min = h * 60 + m
    return open_min <= current_min <= close_min


def is_us_market_hours() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    h = now.hour
    # US market: 22:30-05:00 KST (simplified)
    return h >= 22 or h < 5


class CollectorManager:
    """Manages all collectors and scheduler jobs."""

    def __init__(self, db: Database):
        self.db = db
        self.scheduler = AsyncIOScheduler(timezone="Asia/Seoul")

        # Initialize collectors
        self.kr_stock_polling = NaverStockPollingCollector(db)
        self.kr_stock_integration = NaverStockIntegrationCollector(db)
        self.kr_stock_chart = NaverStockChartCollector(db)
        self.kr_index = NaverKRIndexCollector(db)
        self.foreign_index = NaverForeignIndexCollector(db)
        self.fx = NaverFXCollector(db)
        self.commodity = NaverCommodityCollector(db)
        self.bond = NaverBondCollector(db)
        self.crypto = NaverCryptoCollector(db)

    def setup_jobs(self):
        """Register all scheduled jobs."""

        # Korean stocks + indices: 70s during market hours
        self.scheduler.add_job(
            self._collect_kr_stocks,
            "interval", seconds=POLLING_INTERVAL_SEC,
            id="collect_kr_stocks",
            misfire_grace_time=30,
        )

        self.scheduler.add_job(
            self._collect_kr_indices,
            "interval", seconds=POLLING_INTERVAL_SEC,
            id="collect_kr_indices",
            misfire_grace_time=30,
        )

        # Foreign indices: 70s during US market hours
        self.scheduler.add_job(
            self._collect_foreign_indices,
            "interval", seconds=POLLING_INTERVAL_SEC,
            id="collect_foreign_indices",
            misfire_grace_time=30,
        )

        # FX, commodities, bonds: 5 min always
        self.scheduler.add_job(
            self._collect_market_data,
            "interval", seconds=MARKET_DATA_INTERVAL_SEC,
            id="collect_market_data",
            misfire_grace_time=120,
        )

        # Crypto: 5 min always (24/7)
        self.scheduler.add_job(
            self._collect_crypto,
            "interval", seconds=MARKET_DATA_INTERVAL_SEC,
            id="collect_crypto",
            misfire_grace_time=120,
        )

        # Daily chart + integration: once at 06:00 KST
        self.scheduler.add_job(
            self._collect_daily,
            "cron", hour=DAILY_COLLECT_HOUR, minute=0,
            id="collect_daily",
            misfire_grace_time=3600,
        )

        # DB backup: 04:00 KST
        self.scheduler.add_job(
            self._db_backup,
            "cron", hour=DB_BACKUP_HOUR, minute=0,
            id="db_backup",
            misfire_grace_time=3600,
        )

        # DB compress: 04:30 KST
        self.scheduler.add_job(
            self._db_compress,
            "cron", hour=DB_BACKUP_HOUR, minute=DB_COMPRESS_MINUTES_AFTER,
            id="db_compress",
            misfire_grace_time=3600,
        )

        # Health check: every 5 min
        self.scheduler.add_job(
            self._health_check,
            "interval", seconds=HEALTH_CHECK_INTERVAL_SEC,
            id="health_check",
            misfire_grace_time=60,
        )

        # Signal detection: after each collection (every 70s)
        self.scheduler.add_job(
            self._detect_and_filter_signals,
            "interval", seconds=POLLING_INTERVAL_SEC,
            id="detect_signals",
            misfire_grace_time=30,
        )

        # Prediction evaluation: hourly
        self.scheduler.add_job(
            self._evaluate_predictions,
            "interval", seconds=3600,
            id="evaluate_predictions",
            misfire_grace_time=600,
        )

        # Event calendar check: hourly
        self.scheduler.add_job(
            self._check_events,
            "interval", seconds=3600,
            id="check_events",
            misfire_grace_time=600,
        )

        # Report delivery check: every 30s (poll for new reports)
        self.scheduler.add_job(
            self._check_unsent_reports,
            "interval", seconds=30,
            id="check_unsent_reports",
            misfire_grace_time=10,
        )

        logger.info("Scheduler jobs registered")

    def start(self):
        self.setup_jobs()
        self.scheduler.start()
        logger.info("Scheduler started")

    async def shutdown(self):
        self.scheduler.shutdown(wait=False)
        for collector in [
            self.kr_stock_polling, self.kr_stock_integration,
            self.kr_stock_chart, self.kr_index, self.foreign_index,
            self.fx, self.commodity, self.bond, self.crypto,
        ]:
            await collector.close()

    # ─── Job handlers ───

    async def _collect_kr_stocks(self):
        if not is_kr_market_hours():
            return
        count = await self.kr_stock_polling.collect()
        if count:
            logger.debug("KR stocks: %d records", count)

    async def _collect_kr_indices(self):
        if not is_kr_market_hours():
            return
        count = await self.kr_index.collect()
        if count:
            logger.debug("KR indices: %d records", count)

    async def _collect_foreign_indices(self):
        # Foreign indices are useful even outside US market hours
        count = await self.foreign_index.collect()
        if count:
            logger.debug("Foreign indices: %d records", count)

    async def _collect_market_data(self):
        for collector in [self.fx, self.commodity, self.bond]:
            await collector.collect()

    async def _collect_crypto(self):
        count = await self.crypto.collect()
        if count:
            logger.debug("Crypto: %d records", count)

    async def _collect_daily(self):
        logger.info("Running daily collection (chart + integration)")
        await self.kr_stock_chart.collect()
        await self.kr_stock_integration.collect()

    async def _db_backup(self):
        import shutil
        from config import DB_PATH, BACKUP_DIR
        ts = datetime.now().strftime("%Y%m%d")
        dest = BACKUP_DIR / f"invest_{ts}.db"
        try:
            shutil.copy2(str(DB_PATH), str(dest))
            logger.info("DB backed up to %s", dest)
            # Compress
            import gzip
            with open(str(dest), "rb") as f_in:
                with gzip.open(f"{dest}.gz", "wb") as f_out:
                    f_out.write(f_in.read())
            dest.unlink()  # Remove uncompressed
            # Clean old backups (keep 7 days)
            for old in sorted(BACKUP_DIR.glob("invest_*.db.gz"))[:-7]:
                old.unlink()
                logger.info("Removed old backup: %s", old)
        except Exception as e:
            logger.error("DB backup failed: %s", e)

    async def _db_compress(self):
        self.db.compress_old_realtime()

    async def _detect_and_filter_signals(self):
        from engine.signal_detector import detect_signals
        from engine.signal_filter import run_filter_pipeline
        from config import SIGNAL_QUALITY_TIER2_THRESHOLD

        signals = detect_signals(self.db)
        if not signals:
            return

        filtered = run_filter_pipeline(self.db, signals)

        # Tier 2 alerts for high-quality signals
        for fs in filtered:
            if fs.final_quality >= SIGNAL_QUALITY_TIER2_THRESHOLD:
                logger.info("Tier 2 alert: %s (quality=%.3f)",
                            fs.signal.description, fs.final_quality)
                # TODO: trigger Tier 2 analysis via Claude

    async def _evaluate_predictions(self):
        from engine.prediction_evaluator import evaluate_expired_predictions
        evaluate_expired_predictions(self.db)

    async def _check_events(self):
        from scheduler.event_calendar import check_upcoming_events
        check_upcoming_events(self.db)

    async def _check_unsent_reports(self):
        """Poll for reports that haven't been sent to Telegram yet."""
        unsent = self.db.query(
            "SELECT * FROM reports WHERE notification_sent=0 "
            "AND content_telegram IS NOT NULL")
        for report in unsent:
            logger.info("Unsent report found: %s", report["cycle_id"])
            # TODO: send via Telegram bot
            self.db.execute(
                "UPDATE reports SET notification_sent=1 WHERE id=?",
                (report["id"],))

    async def _health_check(self):
        self.db.update_health("scheduler", "ok")
        counts = self.db.table_counts()
        size = self.db.db_size_mb()
        logger.debug("Health: DB %.1fMB, records=%s", size, counts)
