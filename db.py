"""SQLite database: schema, connection management, CRUD operations."""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager

from config import DB_PATH, KST, DATA_RETENTION_DAYS

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
-- ============================================================
-- PRAGMA settings
-- ============================================================
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

-- ============================================================
-- WATCHLISTS
-- ============================================================
CREATE TABLE IF NOT EXISTS watched_stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL UNIQUE,
    name TEXT,
    market TEXT DEFAULT 'KOSPI',
    country TEXT DEFAULT 'KR',
    reuters_code TEXT,
    asset_type TEXT DEFAULT 'stock',
    added_at TEXT DEFAULT (datetime('now','localtime')),
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS watched_polymarkets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL UNIQUE,
    question TEXT,
    slug TEXT,
    category TEXT,
    end_date TEXT,
    linked_risk_id INTEGER,
    added_at TEXT DEFAULT (datetime('now','localtime')),
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS watched_crypto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,
    name TEXT,
    exchange TEXT DEFAULT 'UPBIT',
    added_at TEXT DEFAULT (datetime('now','localtime')),
    active INTEGER DEFAULT 1
);

-- ============================================================
-- TIME SERIES DATA
-- ============================================================
CREATE TABLE IF NOT EXISTS stock_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    ticker TEXT NOT NULL,
    source TEXT DEFAULT 'naver',
    price REAL,
    open_price REAL,
    high REAL,
    low REAL,
    volume INTEGER,
    change_pct REAL,
    market_cap TEXT,
    per REAL,
    pbr REAL,
    eps REAL,
    foreign_rate REAL,
    foreign_net_buy INTEGER,
    institution_net_buy INTEGER,
    individual_net_buy INTEGER,
    interval TEXT DEFAULT 'realtime',
    UNIQUE(timestamp, ticker, interval)
);

CREATE TABLE IF NOT EXISTS polymarket_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    market_id TEXT NOT NULL,
    yes_price REAL,
    no_price REAL,
    volume_24h REAL,
    liquidity REAL,
    UNIQUE(timestamp, market_id)
);

CREATE TABLE IF NOT EXISTS crypto_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT DEFAULT 'UPBIT',
    price_krw REAL,
    price_usd REAL,
    kimchi_premium REAL,
    change_pct REAL,
    volume REAL,
    market_cap REAL,
    UNIQUE(timestamp, symbol, exchange)
);

CREATE TABLE IF NOT EXISTS market_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    category TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT,
    value REAL,
    change_pct REAL,
    extra_json TEXT,
    UNIQUE(timestamp, category, code)
);

-- ============================================================
-- EVENTS CALENDAR
-- ============================================================
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_date TEXT NOT NULL,
    event_time TEXT,
    name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    importance TEXT DEFAULT 'MED',
    affected_tickers TEXT,
    affected_sectors TEXT,
    consensus TEXT,
    previous TEXT,
    actual TEXT,
    surprise_pct REAL,
    notes TEXT,
    activated_agents TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(event_date, name)
);

-- ============================================================
-- SIGNAL QUALITY
-- ============================================================
CREATE TABLE IF NOT EXISTS signal_quality (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    ticker TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    raw_magnitude REAL,
    volume_score REAL DEFAULT 1.0,
    breadth_score REAL DEFAULT 1.0,
    liquidity_score REAL DEFAULT 1.0,
    dedup_score REAL DEFAULT 1.0,
    stophunt_score REAL DEFAULT 1.0,
    crossasset_score REAL DEFAULT 1.0,
    historical_score REAL DEFAULT 1.0,
    final_quality REAL,
    description TEXT,
    was_real INTEGER,
    evaluated_at TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- CAUSAL CHAIN
-- ============================================================
CREATE TABLE IF NOT EXISTS news_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    headline TEXT NOT NULL,
    source TEXT,
    event_type TEXT,
    magnitude REAL,
    surprise_factor REAL,
    regime_at_time TEXT,
    half_life_hours REAL,
    decay_type TEXT DEFAULT 'exponential',
    affected_tickers TEXT,
    expires_at TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS causal_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    target_ticker TEXT NOT NULL,
    chain_depth INTEGER NOT NULL,
    magnitude_pct REAL NOT NULL,
    delay_hours REAL DEFAULT 0,
    half_life_hours REAL,
    confidence REAL NOT NULL,
    chain_confidence REAL NOT NULL,
    reasoning TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (event_id) REFERENCES news_events(id)
);

-- ============================================================
-- GEOPOLITICAL RISKS (Layer 2)
-- ============================================================
CREATE TABLE IF NOT EXISTS geopolitical_risks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL,
    severity INTEGER NOT NULL,
    risk_premium_json TEXT,
    affected_assets TEXT,
    safe_haven_boost REAL,
    scenarios_json TEXT,
    escalation_prob REAL,
    resolution_prob REAL,
    polymarket_ids TEXT,
    started_at TEXT,
    last_updated TEXT DEFAULT (datetime('now','localtime')),
    resolved_at TEXT
);

-- ============================================================
-- MODEL PARAMETERS
-- ============================================================
CREATE TABLE IF NOT EXISTS model_params (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    param_name TEXT NOT NULL,
    value REAL NOT NULL,
    calibration_factor REAL DEFAULT 1.0,
    description TEXT,
    updated_by TEXT DEFAULT 'initial',
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(category, param_name)
);

-- ============================================================
-- PREDICTIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id TEXT NOT NULL,
    agent_role TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_name TEXT,
    target_type TEXT NOT NULL,
    predicted_direction TEXT,
    predicted_median_pct REAL,
    predicted_ci70_low REAL,
    predicted_ci70_high REAL,
    predicted_ci90_low REAL,
    predicted_ci90_high REAL,
    confidence INTEGER,
    reasoning TEXT,
    horizon TEXT NOT NULL,
    baseline_price REAL NOT NULL,
    evaluation_at TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    actual_price REAL,
    actual_change_pct REAL,
    direction_correct INTEGER,
    median_error_pct REAL,
    in_ci70 INTEGER,
    in_ci90 INTEGER,
    score REAL,
    evaluated_at TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- STRATEGY NOTES
-- ============================================================
CREATE TABLE IF NOT EXISTS strategy_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_role TEXT NOT NULL,
    content TEXT NOT NULL,
    valid_regime TEXT DEFAULT 'all',
    created_at TEXT DEFAULT (datetime('now','localtime')),
    expires_at TEXT,
    decay_confidence REAL DEFAULT 1.0,
    contradicted_count INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1
);

-- ============================================================
-- AGENT ACCURACY
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_accuracy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_role TEXT NOT NULL,
    period TEXT NOT NULL,
    regime TEXT,
    total_predictions INTEGER DEFAULT 0,
    direction_correct INTEGER DEFAULT 0,
    direction_rate REAL,
    avg_median_error REAL,
    ci70_hit_rate REAL,
    ci90_hit_rate REAL,
    calibration_score REAL,
    systematic_bias REAL,
    ensemble_weight REAL DEFAULT 1.0,
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(agent_role, period, regime)
);

-- ============================================================
-- PORTFOLIOS
-- ============================================================
CREATE TABLE IF NOT EXISTS user_portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL UNIQUE,
    name TEXT,
    qty REAL NOT NULL,
    avg_price REAL NOT NULL,
    currency TEXT DEFAULT 'KRW',
    sector TEXT,
    added_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS user_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    ticker TEXT NOT NULL,
    name TEXT,
    action TEXT NOT NULL,
    qty REAL NOT NULL,
    price REAL NOT NULL,
    currency TEXT DEFAULT 'KRW',
    note TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS user_cash (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    currency TEXT NOT NULL UNIQUE,
    amount REAL NOT NULL DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS goguma_portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL UNIQUE,
    name TEXT,
    qty REAL NOT NULL,
    avg_price REAL NOT NULL,
    currency TEXT DEFAULT 'KRW',
    sector TEXT,
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS goguma_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    ticker TEXT NOT NULL,
    name TEXT,
    action TEXT NOT NULL,
    qty REAL NOT NULL,
    price REAL NOT NULL,
    currency TEXT DEFAULT 'KRW',
    reasoning TEXT,
    approved INTEGER DEFAULT 0,
    approved_at TEXT,
    execution_price REAL,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS goguma_cash (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    currency TEXT NOT NULL UNIQUE,
    amount REAL NOT NULL DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS leader_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    name TEXT,
    action TEXT NOT NULL,
    target_price REAL,
    stop_loss REAL,
    confidence INTEGER,
    reasoning TEXT,
    followed INTEGER,
    outcome_pct REAL,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    portfolio_type TEXT NOT NULL,
    total_value_krw REAL,
    total_cost_krw REAL,
    total_pnl_krw REAL,
    total_pnl_pct REAL,
    cash_krw REAL,
    holdings_json TEXT,
    fx_rates_json TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(timestamp, portfolio_type)
);

-- ============================================================
-- TELEGRAM CONTEXT
-- ============================================================
CREATE TABLE IF NOT EXISTS telegram_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER,
    chat_id TEXT NOT NULL,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    reply_to_message_id INTEGER,
    intent TEXT,
    context_type TEXT,
    context_ref TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- PENDING ACTIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS pending_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    params_json TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now','localtime')),
    expires_at TEXT
);

-- ============================================================
-- REPORTS LOG
-- ============================================================
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    triggered_by TEXT,
    agents_activated TEXT,
    content_telegram TEXT,
    content_notion_url TEXT,
    duration_seconds INTEGER,
    notification_sent INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- SYSTEM HEALTH
-- ============================================================
CREATE TABLE IF NOT EXISTS system_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    component TEXT NOT NULL,
    status TEXT NOT NULL,
    last_success TEXT,
    error_count_24h INTEGER DEFAULT 0,
    details TEXT,
    UNIQUE(timestamp, component)
);

CREATE TABLE IF NOT EXISTS deploy_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    branch TEXT,
    commit_hash TEXT,
    changes_summary TEXT,
    status TEXT,
    qa_result TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_stock_prices_ts ON stock_prices(timestamp, ticker);
CREATE INDEX IF NOT EXISTS idx_stock_prices_ticker ON stock_prices(ticker, interval);
CREATE INDEX IF NOT EXISTS idx_poly_prices_ts ON polymarket_prices(timestamp, market_id);
CREATE INDEX IF NOT EXISTS idx_crypto_prices_ts ON crypto_prices(timestamp, symbol);
CREATE INDEX IF NOT EXISTS idx_market_ind_ts ON market_indicators(timestamp, category, code);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date);
CREATE INDEX IF NOT EXISTS idx_signal_quality_ts ON signal_quality(timestamp, ticker);
CREATE INDEX IF NOT EXISTS idx_news_events_ts ON news_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_causal_links_event ON causal_links(event_id);
CREATE INDEX IF NOT EXISTS idx_predictions_cycle ON predictions(cycle_id, agent_role);
CREATE INDEX IF NOT EXISTS idx_predictions_target ON predictions(target_id, status);
CREATE INDEX IF NOT EXISTS idx_predictions_eval ON predictions(evaluation_at, status);
CREATE INDEX IF NOT EXISTS idx_telegram_msg_ts ON telegram_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_telegram_msg_reply ON telegram_messages(reply_to_message_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON portfolio_snapshots(timestamp, portfolio_type);
"""


class Database:
    """SQLite database wrapper with connection pooling and CRUD helpers."""

    def __init__(self, db_path: Path | str = DB_PATH):
        self.db_path = str(db_path)
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    @contextmanager
    def conn(self):
        c = self._get_conn()
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    def _init_schema(self):
        # Use raw connection for schema init (executescript manages its own transactions)
        conn = sqlite3.connect(self.db_path, timeout=10)
        ddl = "\n".join(
            line for line in SCHEMA_SQL.splitlines()
            if not line.strip().upper().startswith("PRAGMA")
        )
        conn.executescript(ddl)
        conn.close()
        logger.info("Database schema initialized: %s", self.db_path)

    def check_integrity(self) -> bool:
        with self.conn() as c:
            result = c.execute("PRAGMA integrity_check").fetchone()
            ok = result[0] == "ok"
            if not ok:
                logger.error("DB integrity check failed: %s", result[0])
            return ok

    # ─── Generic CRUD ───

    def insert(self, table: str, **kwargs) -> int:
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join(["?"] * len(kwargs))
        sql = f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({placeholders})"
        with self.conn() as c:
            cursor = c.execute(sql, list(kwargs.values()))
            return cursor.lastrowid

    def insert_many(self, table: str, rows: list[dict]) -> int:
        if not rows:
            return 0
        cols = ", ".join(rows[0].keys())
        placeholders = ", ".join(["?"] * len(rows[0]))
        sql = f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({placeholders})"
        with self.conn() as c:
            c.executemany(sql, [list(r.values()) for r in rows])
            return len(rows)

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self.conn() as c:
            return c.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        with self.conn() as c:
            return c.execute(sql, params).fetchone()

    def execute(self, sql: str, params: tuple = ()) -> int:
        with self.conn() as c:
            cursor = c.execute(sql, params)
            return cursor.rowcount

    # ─── Watchlist Operations ───

    def get_watched_stocks(self, country: str = "") -> list[sqlite3.Row]:
        if country:
            return self.query(
                "SELECT * FROM watched_stocks WHERE active=1 AND country=?",
                (country,),
            )
        return self.query("SELECT * FROM watched_stocks WHERE active=1")

    def get_watched_crypto(self) -> list[sqlite3.Row]:
        return self.query("SELECT * FROM watched_crypto WHERE active=1")

    def get_watched_polymarkets(self) -> list[sqlite3.Row]:
        return self.query("SELECT * FROM watched_polymarkets WHERE active=1")

    def add_stock(self, ticker: str, name: str = "", market: str = "KOSPI",
                  country: str = "KR", reuters_code: str = "",
                  asset_type: str = "stock") -> int:
        return self.insert(
            "watched_stocks",
            ticker=ticker, name=name, market=market, country=country,
            reuters_code=reuters_code, asset_type=asset_type,
        )

    def remove_stock(self, ticker: str) -> int:
        return self.execute(
            "UPDATE watched_stocks SET active=0 WHERE ticker=?", (ticker,)
        )

    # ─── Price Operations ───

    def save_stock_prices(self, records: list[dict]) -> int:
        return self.insert_many("stock_prices", records)

    def save_crypto_prices(self, records: list[dict]) -> int:
        return self.insert_many("crypto_prices", records)

    def save_market_indicators(self, records: list[dict]) -> int:
        return self.insert_many("market_indicators", records)

    def get_latest_price(self, ticker: str) -> sqlite3.Row | None:
        return self.query_one(
            "SELECT * FROM stock_prices WHERE ticker=? ORDER BY timestamp DESC LIMIT 1",
            (ticker,),
        )

    def get_latest_indicator(self, category: str, code: str) -> sqlite3.Row | None:
        return self.query_one(
            "SELECT * FROM market_indicators WHERE category=? AND code=? "
            "ORDER BY timestamp DESC LIMIT 1",
            (category, code),
        )

    def get_price_history(self, ticker: str, interval: str = "daily",
                          days: int = 90) -> list[sqlite3.Row]:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        return self.query(
            "SELECT * FROM stock_prices WHERE ticker=? AND interval=? "
            "AND timestamp>=? ORDER BY timestamp",
            (ticker, interval, cutoff),
        )

    # ─── System Health ───

    def update_health(self, component: str, status: str, details: str = ""):
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        self.execute(
            "INSERT OR REPLACE INTO system_health "
            "(timestamp, component, status, last_success, details) "
            "VALUES (?, ?, ?, ?, ?)",
            (now, component, status,
             now if status == "ok" else None, details),
        )

    # ─── Telegram Context ───

    def save_message(self, message_id: int, chat_id: str, role: str,
                     text: str, reply_to: int | None = None,
                     intent: str = "", context_type: str = "",
                     context_ref: str = "") -> int:
        return self.insert(
            "telegram_messages",
            message_id=message_id, chat_id=chat_id, role=role,
            text=text, reply_to_message_id=reply_to, intent=intent,
            context_type=context_type, context_ref=context_ref,
        )

    def get_recent_messages(self, chat_id: str, limit: int = 10) -> list[sqlite3.Row]:
        return self.query(
            "SELECT * FROM telegram_messages WHERE chat_id=? "
            "ORDER BY created_at DESC LIMIT ?",
            (chat_id, limit),
        )

    def get_message_by_telegram_id(self, message_id: int) -> sqlite3.Row | None:
        return self.query_one(
            "SELECT * FROM telegram_messages WHERE message_id=?",
            (message_id,),
        )

    # ─── Pending Actions ───

    def create_pending_action(self, chat_id: str, action_type: str,
                               params: dict, description: str) -> int:
        expires = (datetime.now() + timedelta(minutes=5)).isoformat()
        return self.insert(
            "pending_actions",
            chat_id=chat_id, action_type=action_type,
            params_json=json.dumps(params, ensure_ascii=False),
            description=description, expires_at=expires,
        )

    def get_pending_action(self, chat_id: str) -> sqlite3.Row | None:
        return self.query_one(
            "SELECT * FROM pending_actions "
            "WHERE chat_id=? AND status='pending' AND expires_at>datetime('now','localtime') "
            "ORDER BY created_at DESC LIMIT 1",
            (chat_id,),
        )

    def resolve_pending_action(self, action_id: int, status: str = "approved"):
        self.execute(
            "UPDATE pending_actions SET status=? WHERE id=?",
            (status, action_id),
        )

    # ─── DB Maintenance ───

    def compress_old_realtime(self, days: int = DATA_RETENTION_DAYS):
        """Compress realtime data older than N days into daily aggregates."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        # Count records to compress
        count = self.query_one(
            "SELECT COUNT(*) as cnt FROM stock_prices "
            "WHERE interval='realtime' AND timestamp<?",
            (cutoff,),
        )
        if count and count["cnt"] > 0:
            logger.info("Compressing %d realtime records older than %s",
                        count["cnt"], cutoff)
            # Delete old realtime data (daily data already exists from daily collection)
            self.execute(
                "DELETE FROM stock_prices WHERE interval='realtime' AND timestamp<?",
                (cutoff,),
            )
            logger.info("Compression complete")

    def db_size_mb(self) -> float:
        return Path(self.db_path).stat().st_size / (1024 * 1024)

    def table_counts(self) -> dict[str, int]:
        tables = [
            "stock_prices", "crypto_prices", "polymarket_prices",
            "market_indicators", "predictions", "signal_quality",
            "telegram_messages", "events",
        ]
        counts = {}
        for t in tables:
            row = self.query_one(f"SELECT COUNT(*) as cnt FROM {t}")
            counts[t] = row["cnt"] if row else 0
        return counts


def check_health():
    """Standalone health check for Docker healthcheck."""
    db = Database()
    ok = db.check_integrity()
    if not ok:
        raise SystemExit(1)
    # Check if data was collected recently
    row = db.query_one(
        "SELECT MAX(timestamp) as ts FROM stock_prices"
    )
    if row and row["ts"]:
        last = datetime.fromisoformat(row["ts"])
        age = datetime.now() - last
        if age > timedelta(minutes=10):
            logger.warning("Last data collection was %s ago", age)
    raise SystemExit(0)


if __name__ == "__main__":
    check_health()
