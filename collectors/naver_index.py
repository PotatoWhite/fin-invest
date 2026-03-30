"""Naver index collector: Korean indices (polling) + Foreign indices (nation API)."""

import logging
from datetime import datetime

from collectors.base import BaseCollector
from config import NAVER_POLLING, NAVER_INDEX_NATION, NAVER_CHART_DOMESTIC_INDEX

logger = logging.getLogger(__name__)

KR_INDICES = ["KOSPI", "KOSDAQ"]
FOREIGN_NATIONS = {"USA": [".DJI", ".IXIC", ".INX", ".SOX", ".VIX"]}


class NaverKRIndexCollector(BaseCollector):
    """Korean index real-time via polling API."""

    name = "naver_kr_index"

    async def _fetch(self) -> list[dict]:
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        records = []

        query = ",".join(f"SERVICE_INDEX:{idx}" for idx in KR_INDICES)
        data = await self._get_json(NAVER_POLLING, params={"query": query})

        for area in data.get("result", {}).get("areas", []):
            for item in area.get("datas", []):
                code = item.get("cd", "")
                if not code:
                    continue
                # Index values are stored as integers (e.g., 527730 = 5277.30)
                nv = item.get("nv")
                value = nv / 100.0 if nv and nv > 10000 else nv
                records.append({
                    "timestamp": now,
                    "category": "index",
                    "code": code,
                    "name": code,
                    "value": value,
                    "change_pct": item.get("cr"),
                })

        return records

    async def _save(self, records: list[dict]) -> int:
        return self.db.save_market_indicators(records)


class NaverForeignIndexCollector(BaseCollector):
    """Foreign indices (US: DJI, NASDAQ, S&P500, SOX, VIX) via nation API."""

    name = "naver_foreign_index"

    async def _fetch(self) -> list[dict]:
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        records = []

        for nation, expected_codes in FOREIGN_NATIONS.items():
            url = NAVER_INDEX_NATION.format(nation=nation)
            try:
                items = await self._get_json(url)
            except Exception as e:
                logger.warning("Foreign index fetch failed for %s: %s", nation, e)
                continue

            for item in items if isinstance(items, list) else []:
                code = item.get("reutersCode", "")
                close_str = item.get("closePrice", "")
                try:
                    value = float(str(close_str).replace(",", ""))
                except (ValueError, TypeError):
                    value = None

                change_str = item.get("fluctuationsRatio", "")
                try:
                    change = float(str(change_str).replace(",", ""))
                except (ValueError, TypeError):
                    change = None

                records.append({
                    "timestamp": now,
                    "category": "index",
                    "code": code,
                    "name": item.get("indexNameEng", item.get("indexName", "")),
                    "value": value,
                    "change_pct": change,
                })

        return records

    async def _save(self, records: list[dict]) -> int:
        return self.db.save_market_indicators(records)
