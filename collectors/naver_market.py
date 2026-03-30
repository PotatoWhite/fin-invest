"""Naver market data: FX, commodities, bonds, crypto via front-api."""

import logging
from datetime import datetime

from collectors.base import BaseCollector
from config import (
    NAVER_FRONT_EXCHANGE, NAVER_FRONT_ENERGY, NAVER_FRONT_METALS,
    NAVER_FRONT_BOND, NAVER_FRONT_CRYPTO, NAVER_FRONT_MAJORS,
)

logger = logging.getLogger(__name__)


class NaverFXCollector(BaseCollector):
    """Exchange rates via front-api."""

    name = "naver_fx"

    async def _fetch(self) -> list[dict]:
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        data = await self._get_json(NAVER_FRONT_EXCHANGE)
        records = []

        items = data.get("result", []) if isinstance(data, dict) else data
        if not isinstance(items, list):
            items = []

        for item in items:
            code = item.get("reutersCode", "")
            if not code:
                continue
            records.append({
                "timestamp": now,
                "category": "fx",
                "code": code,
                "name": item.get("name", ""),
                "value": _parse_price(item.get("closePrice", "")),
                "change_pct": _parse_price(item.get("fluctuationsRatio", "")),
            })

        return records

    async def _save(self, records: list[dict]) -> int:
        return self.db.save_market_indicators(records)


class NaverCommodityCollector(BaseCollector):
    """Energy + metals via front-api."""

    name = "naver_commodity"

    async def _fetch(self) -> list[dict]:
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        records = []

        for url, cat in [(NAVER_FRONT_ENERGY, "commodity"),
                         (NAVER_FRONT_METALS, "commodity")]:
            try:
                data = await self._get_json(url)
            except Exception as e:
                logger.warning("Commodity fetch failed for %s: %s", url, e)
                continue

            result = data.get("result", {}) if isinstance(data, dict) else {}
            items = result.get("mainList", []) if isinstance(result, dict) else []

            for item in items:
                code = item.get("symbolCode", item.get("reutersCode", ""))
                if not code:
                    continue
                records.append({
                    "timestamp": now,
                    "category": cat,
                    "code": code,
                    "name": item.get("name", ""),
                    "value": _parse_price(item.get("closePrice", "")),
                    "change_pct": _parse_price(item.get("fluctuationsRatio", "")),
                    "extra_json": None,
                })

        return records

    async def _save(self, records: list[dict]) -> int:
        return self.db.save_market_indicators(records)


class NaverBondCollector(BaseCollector):
    """Bond yields via front-api."""

    name = "naver_bond"

    async def _fetch(self) -> list[dict]:
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        records = []

        for country in ["USA", "KOR"]:
            try:
                data = await self._get_json(
                    NAVER_FRONT_BOND, params={"countryCode": country})
            except Exception as e:
                logger.warning("Bond fetch failed for %s: %s", country, e)
                continue

            items = data.get("result", []) if isinstance(data, dict) else data
            for item in items:
                code = item.get("reutersCode", "")
                if not code:
                    continue
                records.append({
                    "timestamp": now,
                    "category": "bond",
                    "code": code,
                    "name": item.get("name", ""),
                    "value": _parse_price(item.get("closePrice", "")),
                    "change_pct": _parse_price(item.get("fluctuationsRatio", "")),
                })

        return records

    async def _save(self, records: list[dict]) -> int:
        return self.db.save_market_indicators(records)


class NaverCryptoCollector(BaseCollector):
    """Crypto prices (KRW) via front-api/crypto/top."""

    name = "naver_crypto"

    async def _fetch(self) -> list[dict]:
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        watched = self.db.get_watched_crypto()
        if not watched:
            return []

        watched_symbols = {c["symbol"] for c in watched}

        try:
            data = await self._get_json(
                NAVER_FRONT_CRYPTO,
                params={"exchangeType": "UPBIT", "page": "1", "pageSize": "50"})
        except Exception as e:
            logger.warning("Crypto fetch failed: %s", e)
            return []

        records = []
        result = data.get("result", {}) if isinstance(data, dict) else {}
        items = result.get("contents", []) if isinstance(result, dict) else []

        for item in items:
            symbol = item.get("nfTicker", "")
            if not symbol or symbol not in watched_symbols:
                continue
            records.append({
                "timestamp": now,
                "symbol": symbol,
                "exchange": "UPBIT",
                "price_krw": item.get("tradePrice"),
                "kimchi_premium": item.get("krwPremiumRate"),
                "change_pct": item.get("changeRate"),
                "volume": item.get("accumulatedTradingValue"),
                "market_cap": item.get("marketCap"),
            })

        return records

    async def _save(self, records: list[dict]) -> int:
        return self.db.save_crypto_prices(records)


def _parse_price(s) -> float | None:
    if s is None:
        return None
    try:
        return float(str(s).replace(",", ""))
    except (ValueError, TypeError):
        return None
