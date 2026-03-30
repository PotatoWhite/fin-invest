"""Base collector with retry, fallback, and cooldown logic."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta

import aiohttp

from config import MAX_CONSECUTIVE_FAILURES, COOLDOWN_MINUTES
from db import Database

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """Abstract base for all data collectors."""

    name: str = "base"

    def __init__(self, db: Database):
        self.db = db
        self.session: aiohttp.ClientSession | None = None
        self.error_count = 0
        self.cooldown_until: datetime | None = None

    async def ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"User-Agent": "fin-invest/1.0"},
            )

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def collect(self) -> int:
        """Run collection cycle. Returns number of records saved."""
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            remaining = (self.cooldown_until - datetime.now()).seconds
            logger.debug("%s in cooldown (%ds remaining)", self.name, remaining)
            return 0

        await self.ensure_session()
        try:
            records = await self._fetch()
            count = await self._save(records)
            self.error_count = 0
            self.db.update_health(f"collector_{self.name}", "ok")
            return count
        except Exception as e:
            self.error_count += 1
            logger.warning("%s fetch failed (%d/%d): %s",
                           self.name, self.error_count,
                           MAX_CONSECUTIVE_FAILURES, e)

            if self.error_count >= MAX_CONSECUTIVE_FAILURES:
                self.cooldown_until = datetime.now() + timedelta(minutes=COOLDOWN_MINUTES)
                logger.error("%s entering cooldown for %d minutes",
                             self.name, COOLDOWN_MINUTES)
                self.db.update_health(
                    f"collector_{self.name}", "error",
                    f"Cooldown until {self.cooldown_until.isoformat()}")

            # Try fallback
            try:
                records = await self._fallback()
                count = await self._save(records)
                if count > 0:
                    logger.info("%s fallback succeeded: %d records", self.name, count)
                    self.db.update_health(
                        f"collector_{self.name}", "warning", "Using fallback")
                return count
            except Exception as fe:
                logger.error("%s fallback also failed: %s", self.name, fe)
                return 0

    @abstractmethod
    async def _fetch(self) -> list[dict]:
        """Fetch data from primary source. Must be implemented by subclasses."""
        ...

    async def _fallback(self) -> list[dict]:
        """Fetch from fallback source. Override in subclasses that have fallbacks."""
        return []

    async def _save(self, records: list[dict]) -> int:
        """Save records to DB. Override if custom save logic needed."""
        return 0

    async def _get_json(self, url: str, params: dict | None = None) -> dict:
        """Helper: fetch JSON from URL."""
        await self.ensure_session()
        async with self.session.get(url, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()
