"""Configuration and environment variable loading."""

import os
from pathlib import Path
from datetime import timezone, timedelta

# ─── Paths ───
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
BACKUP_DIR = BASE_DIR / "backups"
DB_PATH = DATA_DIR / "invest.db"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)

# ─── Environment Variables ───
def _load_env():
    """Load .env file if it exists."""
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

_load_env()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")

# ─── Timezone ───
KST = timezone(timedelta(hours=9))

# ─── Naver API Endpoints ───
NAVER_STOCK_BASIC = "https://m.stock.naver.com/api/stock/{code}/basic"
NAVER_STOCK_INTEGRATION = "https://m.stock.naver.com/api/stock/{code}/integration"
NAVER_CHART_DOMESTIC = "https://api.stock.naver.com/chart/domestic/item/{code}"
NAVER_CHART_FOREIGN = "https://api.stock.naver.com/chart/foreign/item/{code}"
NAVER_CHART_DOMESTIC_INDEX = "https://api.stock.naver.com/chart/domestic/index/{code}"
NAVER_CHART_FOREIGN_INDEX = "https://api.stock.naver.com/chart/foreign/index/{code}"
NAVER_POLLING = "https://polling.finance.naver.com/api/realtime"
NAVER_INDEX_NATION = "https://api.stock.naver.com/index/nation/{nation}"
NAVER_FRONT_MAJORS = "https://m.stock.naver.com/front-api/marketIndex/majors"
NAVER_FRONT_EXCHANGE = "https://m.stock.naver.com/front-api/marketIndex/exchange/main"
NAVER_FRONT_ENERGY = "https://m.stock.naver.com/front-api/marketIndex/energy"
NAVER_FRONT_METALS = "https://m.stock.naver.com/front-api/marketIndex/metals"
NAVER_FRONT_BOND = "https://m.stock.naver.com/front-api/marketIndex/bondList"
NAVER_FRONT_CRYPTO = "https://m.stock.naver.com/front-api/crypto/top"
NAVER_LEGACY_CHART = "https://fchart.stock.naver.com/sise.nhn"
NAVER_ETF_LIST = "https://finance.naver.com/api/sise/etfItemList.nhn"

# ─── Collection Intervals ───
POLLING_INTERVAL_SEC = 70          # Naver recommended
MARKET_DATA_INTERVAL_SEC = 300     # 5 min for FX/commodity/bond/crypto
DAILY_COLLECT_HOUR = 6             # 06:00 KST for daily chart + US fundamentals
DB_BACKUP_HOUR = 4                 # 04:00 KST
DB_COMPRESS_MINUTES_AFTER = 30     # 04:30 KST
HEALTH_CHECK_INTERVAL_SEC = 300    # 5 min

# ─── Market Hours (KST) ───
KR_MARKET_OPEN = (8, 55)          # 08:55
KR_MARKET_CLOSE = (15, 35)        # 15:35
US_MARKET_OPEN_KST = (22, 30)     # 22:30 (summer) / 23:30 (winter)
US_MARKET_CLOSE_KST = (5, 0)      # 05:00 (summer) / 06:00 (winter)

# ─── Signal Thresholds ───
SIGNAL_PRICE_MOVE_THRESHOLD = 2.0  # % change to trigger signal
SIGNAL_VOLUME_SPIKE_MULTIPLIER = 2.0
SIGNAL_QUALITY_TIER2_THRESHOLD = 0.7
SIGNAL_QUALITY_IGNORE_THRESHOLD = 0.4

# ─── Collector Settings ───
MAX_CONSECUTIVE_FAILURES = 5
COOLDOWN_MINUTES = 30
DATA_RETENTION_DAYS = 90           # Compress realtime data older than this

# ─── Claude Code ───
CLAUDE_PATH = os.environ.get("CLAUDE_PATH", "claude")
CLAUDE_DEFAULT_MODEL = "sonnet"
CLAUDE_AGENT_MODELS = {
    "leader": "opus",
    "goguma": "opus",
}
CLAUDE_MAX_CONCURRENT = 3
CLAUDE_SUBPROCESS_TIMEOUT = 300    # seconds
