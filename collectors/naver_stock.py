"""Naver stock collector: polling (70s), integration (daily), chart (backfill)."""

import logging
from datetime import datetime

from collectors.base import BaseCollector
from config import (
    NAVER_POLLING, NAVER_STOCK_INTEGRATION, NAVER_CHART_DOMESTIC,
    NAVER_LEGACY_CHART, KST,
)
from db import Database

logger = logging.getLogger(__name__)


class NaverStockPollingCollector(BaseCollector):
    """Real-time stock prices via Naver polling API (70s interval)."""

    name = "naver_stock_polling"

    async def _fetch(self) -> list[dict]:
        stocks = self.db.get_watched_stocks(country="KR")
        if not stocks:
            return []

        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        records = []

        # Batch query: up to 20 tickers per request
        tickers = [s["ticker"] for s in stocks]
        for i in range(0, len(tickers), 20):
            batch = tickers[i:i + 20]
            query = ",".join(f"SERVICE_ITEM:{t}" for t in batch)
            data = await self._get_json(NAVER_POLLING, params={"query": query})

            for area in data.get("result", {}).get("areas", []):
                for item in area.get("datas", []):
                    code = item.get("cd", "")
                    if not code:
                        continue
                    records.append({
                        "timestamp": now,
                        "ticker": code,
                        "source": "naver_polling",
                        "price": item.get("nv"),
                        "open_price": item.get("ov"),
                        "high": item.get("hv"),
                        "low": item.get("lv"),
                        "volume": item.get("aq"),
                        "change_pct": item.get("cr"),
                        "interval": "realtime",
                    })

        return records

    async def _save(self, records: list[dict]) -> int:
        return self.db.save_stock_prices(records)


class NaverStockIntegrationCollector(BaseCollector):
    """Full stock fundamentals via Naver integration API (daily)."""

    name = "naver_stock_integration"

    async def _fetch(self) -> list[dict]:
        stocks = self.db.get_watched_stocks(country="KR")
        if not stocks:
            return []

        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        records = []

        for stock in stocks:
            ticker = stock["ticker"]
            url = NAVER_STOCK_INTEGRATION.format(code=ticker)
            try:
                data = await self._get_json(url)
            except Exception as e:
                logger.warning("Integration fetch failed for %s: %s", ticker, e)
                continue

            # Parse totalInfos
            info = {}
            for item in data.get("totalInfos", []):
                code = item.get("code", "")
                val = item.get("value", "")
                info[code] = val

            # Parse dealTrendInfos (latest day)
            deal_trends = data.get("dealTrendInfos", [])
            latest_trend = deal_trends[0] if deal_trends else {}

            # Parse close price from basic data
            close_price = _parse_number(info.get("lastClosePrice", ""))

            record = {
                "timestamp": now,
                "ticker": ticker,
                "source": "naver_integration",
                "price": close_price,
                "open_price": _parse_number(info.get("openPrice", "")),
                "high": _parse_number(info.get("highPrice", "")),
                "low": _parse_number(info.get("lowPrice", "")),
                "volume": _parse_int(info.get("accumulatedTradingVolume", "")),
                "market_cap": info.get("marketValue", ""),
                "per": _parse_float(info.get("per", "")),
                "pbr": _parse_float(info.get("pbr", "")),
                "eps": _parse_number(info.get("eps", "")),
                "foreign_rate": _parse_float(info.get("foreignRate", "")),
                "foreign_net_buy": _parse_int(
                    latest_trend.get("foreignerPureBuyQuant", "")),
                "institution_net_buy": _parse_int(
                    latest_trend.get("organPureBuyQuant", "")),
                "individual_net_buy": _parse_int(
                    latest_trend.get("individualPureBuyQuant", "")),
                "interval": "daily",
            }
            records.append(record)

            # Update watched_stocks metadata
            name = data.get("stockName", stock["name"])
            if name:
                self.db.execute(
                    "UPDATE watched_stocks SET name=? WHERE ticker=?",
                    (name, ticker),
                )

        return records

    async def _save(self, records: list[dict]) -> int:
        return self.db.save_stock_prices(records)


class NaverStockChartCollector(BaseCollector):
    """Daily OHLCV chart data. Used for backfill and daily updates."""

    name = "naver_stock_chart"

    async def _fetch(self) -> list[dict]:
        stocks = self.db.get_watched_stocks(country="KR")
        if not stocks:
            return []

        records = []
        for stock in stocks:
            ticker = stock["ticker"]
            url = NAVER_CHART_DOMESTIC.format(code=ticker)
            try:
                data = await self._get_json(url, params={"periodType": "dayCandle"})
            except Exception as e:
                logger.warning("Chart fetch failed for %s: %s", ticker, e)
                continue

            for p in data.get("priceInfos", []):
                records.append({
                    "timestamp": p.get("localDate", ""),
                    "ticker": ticker,
                    "source": "naver_chart",
                    "price": p.get("closePrice"),
                    "open_price": p.get("openPrice"),
                    "high": p.get("highPrice"),
                    "low": p.get("lowPrice"),
                    "volume": p.get("accumulatedTradingVolume"),
                    "foreign_rate": p.get("foreignRetentionRate"),
                    "interval": "daily",
                })

        return records

    async def _save(self, records: list[dict]) -> int:
        return self.db.save_stock_prices(records)

    async def backfill(self, ticker: str, count: int = 2500):
        """Backfill historical data using legacy fchart API."""
        url = NAVER_LEGACY_CHART
        params = {
            "symbol": ticker,
            "timeframe": "day",
            "count": str(count),
            "requestType": "0",
        }
        try:
            await self.ensure_session()
            async with self.session.get(url, params=params) as resp:
                text = await resp.text()

            # Parse XML: <item data="DATE|OPEN|HIGH|LOW|CLOSE|VOLUME" />
            import re
            records = []
            for match in re.finditer(r'data="([^"]+)"', text):
                parts = match.group(1).split("|")
                if len(parts) >= 6:
                    records.append({
                        "timestamp": parts[0],
                        "ticker": ticker,
                        "source": "naver_legacy",
                        "open_price": _parse_number(parts[1]),
                        "high": _parse_number(parts[2]),
                        "low": _parse_number(parts[3]),
                        "price": _parse_number(parts[4]),
                        "volume": _parse_int(parts[5]),
                        "interval": "daily",
                    })

            count = self.db.save_stock_prices(records)
            logger.info("Backfilled %d daily records for %s", count, ticker)
            return count

        except Exception as e:
            logger.error("Backfill failed for %s: %s", ticker, e)
            return 0


def _parse_number(s: str) -> float | None:
    """Parse Korean-formatted number: '176,300' -> 176300.0"""
    if not s:
        return None
    try:
        return float(str(s).replace(",", "").replace("배", "").replace("%", ""))
    except (ValueError, TypeError):
        return None


def _parse_int(s: str) -> int | None:
    v = _parse_number(s)
    return int(v) if v is not None else None


def _parse_float(s: str) -> float | None:
    return _parse_number(s)
