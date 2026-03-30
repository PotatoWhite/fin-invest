"""Database maintenance: backup, compression, integrity check."""

import gzip
import logging
import shutil
from datetime import datetime
from pathlib import Path

from config import DB_PATH, BACKUP_DIR, DATA_RETENTION_DAYS
from db import Database

logger = logging.getLogger(__name__)


def backup_daily(db: Database) -> str | None:
    """Create daily compressed backup."""
    ts = datetime.now().strftime("%Y%m%d")
    dest = BACKUP_DIR / f"invest_{ts}.db"
    gz_dest = Path(f"{dest}.gz")

    try:
        shutil.copy2(str(DB_PATH), str(dest))
        with open(str(dest), "rb") as f_in:
            with gzip.open(str(gz_dest), "wb") as f_out:
                f_out.write(f_in.read())
        dest.unlink()
        logger.info("Daily backup: %s (%.1fMB)",
                     gz_dest, gz_dest.stat().st_size / 1024 / 1024)

        # Clean old daily backups (keep 7)
        daily_backups = sorted(BACKUP_DIR.glob("invest_*.db.gz"))
        for old in daily_backups[:-7]:
            old.unlink()
            logger.info("Removed old backup: %s", old.name)

        return str(gz_dest)
    except Exception as e:
        logger.error("Backup failed: %s", e)
        return None


def backup_weekly(db: Database) -> str | None:
    """Create weekly backup (keep 4 weeks)."""
    weekly_dir = BACKUP_DIR / "weekly"
    weekly_dir.mkdir(exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d")
    dest = weekly_dir / f"invest_{ts}.db.gz"

    try:
        with open(str(DB_PATH), "rb") as f_in:
            with gzip.open(str(dest), "wb") as f_out:
                f_out.write(f_in.read())
        logger.info("Weekly backup: %s", dest)

        # Keep 4 weeks
        weekly_backups = sorted(weekly_dir.glob("invest_*.db.gz"))
        for old in weekly_backups[:-4]:
            old.unlink()

        return str(dest)
    except Exception as e:
        logger.error("Weekly backup failed: %s", e)
        return None


def compress_old_data(db: Database) -> int:
    """Compress realtime data older than retention period to daily aggregates."""
    return db.compress_old_realtime(DATA_RETENTION_DAYS)


def check_integrity(db: Database) -> bool:
    """Run integrity check and return status."""
    return db.check_integrity()


def get_db_stats(db: Database) -> dict:
    """Get comprehensive DB statistics."""
    return {
        "size_mb": round(db.db_size_mb(), 2),
        "tables": db.table_counts(),
        "integrity": db.check_integrity(),
        "backup_dir": str(BACKUP_DIR),
        "backup_count": len(list(BACKUP_DIR.glob("*.gz"))),
    }
