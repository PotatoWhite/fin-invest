# fin-invest System Architecture -- Complete Design

## 1. Project Structure

```
invest/
├── .claude/
│   ├── settings.local.json          # MCP server registration, permissions
│   ├── agents/
│   │   ├── leader.md                # Leader agent (Opus + Extended Thinking)
│   │   ├── goguma.md                # Goguma agent (Opus, independent)
│   │   ├── micro-expert.md          # Micro/fundamentals expert (Sonnet)
│   │   ├── macro-expert.md          # Macro expert (Sonnet)
│   │   ├── finance-expert.md        # Financial markets expert (Sonnet)
│   │   ├── commodities-expert.md    # Commodities expert (Sonnet)
│   │   ├── usmarket-expert.md       # US market expert (Sonnet)
│   │   ├── global-expert.md         # Global markets expert (Sonnet)
│   │   ├── korea-expert.md          # Korean market expert (Sonnet)
│   │   ├── improvement.md           # Improvement agent (Sonnet)
│   │   ├── qa.md                    # QA agent (Sonnet)
│   │   └── devops.md                # DevOps agent (Sonnet)
│   └── plans/                       # Claude Code planning workspace
│
├── .env                             # TELEGRAM_BOT_TOKEN, CHAT_ID, NOTION_TOKEN
├── .gitignore
├── CLAUDE.md                        # Master instructions for Claude Code
├── REQUIREMENTS.md                  # Requirements doc (reference)
├── NAVER_API_RESEARCH.md            # API endpoints doc (reference)
├── requirements.txt                 # Python dependencies
│
├── config.py                        # Settings, env loading, constants
├── main.py                          # Entry point: asyncio event loop
├── db.py                            # SQLite schema, connection, CRUD, migrations
│
├── collectors/
│   ├── __init__.py
│   ├── base.py                      # BaseCollector ABC (retry, fallback, rate limit)
│   ├── naver_stock.py               # Korean stocks: basic, integration, chart, polling
│   ├── naver_index.py               # Korean + foreign indices
│   ├── naver_market.py              # FX, commodities, bonds, crypto (front-api)
│   ├── yfinance_fallback.py         # US fundamentals, historical FX/commodity/bond/crypto
│   ├── polymarket.py                # Polymarket CLOB/Gamma API
│   ├── upbit.py                     # Upbit crypto OHLCV history
│   ├── finnhub.py                   # Finnhub: US news, economic calendar (Phase 3+)
│   └── naver_news.py                # Naver News RSS for Korean stock news (Phase 3+)
│
├── engine/
│   ├── __init__.py
│   ├── signal_detector.py           # Anomaly detection (price/volume spikes)
│   ├── signal_filter.py             # 7-filter pipeline
│   ├── impact_calculator.py         # 3-Layer model (event + geopolitical + polymarket)
│   ├── decay_engine.py              # Half-life decay functions (exponential, step, dual)
│   ├── technical.py                 # Technical indicators (SMA, RSI, MACD, Bollinger, Fibonacci)
│   ├── regime_detector.py           # Regime detection (VIX, spread, breadth, flow)
│   └── prediction_evaluator.py      # Evaluate expired predictions, update accuracy
│
├── bot/
│   ├── __init__.py
│   ├── telegram.py                  # Async Telegram bot (python-telegram-bot 22.x)
│   ├── intent_classifier.py         # 2-stage intent: keyword Stage 1 + Claude Stage 2
│   ├── context_manager.py           # Conversation context (DB-backed, reply tracking)
│   ├── formatters.py                # Message formatting (Markdown, chunking)
│   └── claude_bridge.py             # Subprocess bridge: Python <-> Claude Code CLI
│
├── mcp_server.py                    # FastMCP server (20+ tools)
│
├── scheduler/
│   ├── __init__.py
│   ├── jobs.py                      # APScheduler job definitions
│   ├── event_calendar.py            # Event calendar manager (D-7/3/1/0 triggers)
│   └── report_orchestrator.py       # Report cycle: prepare data -> trigger Claude -> collect
│
├── notion/
│   ├── __init__.py
│   ├── client.py                    # Notion API wrapper
│   ├── report_publisher.py          # Publish reports to Notion pages
│   └── dashboard_updater.py         # Update dashboard databases
│
├── ops/
│   ├── __init__.py
│   ├── health_monitor.py            # System health checks
│   ├── db_maintenance.py            # Backup, compression, integrity
│   └── deploy.py                    # Git-based deploy/rollback
│
├── tests/
│   ├── __init__.py
│   ├── test_collectors.py
│   ├── test_signal_filter.py
│   ├── test_impact_calculator.py
│   ├── test_technical.py
│   ├── test_regime.py
│   ├── test_db.py
│   └── test_telegram_intent.py
│
├── scripts/
│   ├── init_db.py                   # Initialize DB with schema + seed model_params
│   ├── backfill_history.py          # One-time historical data backfill
│   └── migrate_from_potato_fin.py   # Migrate trades/snapshots from potato-fin
│
├── backups/                         # DB backups (gitignored)
├── logs/                            # Log files (gitignored)
│
├── Dockerfile                       # Python daemon image
├── docker-compose.yml               # Service orchestration
├── .dockerignore
└── invest.service                   # systemd unit file (Docker host에서 compose 관리)
```

---

## Docker 구성

### Dockerfile
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl && rm -rf /var/lib/apt/lists/*

# Claude Code CLI 설치
RUN curl -fsSL https://claude.ai/install.sh | sh

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# DB 및 로그 볼륨
VOLUME ["/app/data", "/app/logs", "/app/backups"]

# MCP 서버는 Claude Code가 별도 프로세스로 실행
# main.py는 봇 + 스케줄러 + 헬스 모니터
CMD ["python", "main.py"]
```

### docker-compose.yml
```yaml
services:
  invest:
    build: .
    container_name: fin-invest
    restart: always
    env_file: .env
    volumes:
      - ./data:/app/data          # invest.db 영속화
      - ./backups:/app/backups    # DB 백업 영속화
      - ./logs:/app/logs          # 로그 영속화
      - ./.claude:/app/.claude    # Claude Code 설정 + 에이전트 (호스트와 공유)
    environment:
      - TZ=Asia/Seoul
    # 헬스체크: 마지막 데이터 수집이 5분 이내인지
    healthcheck:
      test: ["CMD", "python", "-c", "import db; db.check_health()"]
      interval: 5m
      timeout: 10s
      retries: 3
```

### 볼륨 전략
```
호스트                    컨테이너
./data/invest.db    →    /app/data/invest.db      # DB 영속화
./backups/          →    /app/backups/             # 백업 영속화
./logs/             →    /app/logs/                # 로그 영속화
./.claude/          →    /app/.claude/             # 에이전트 + MCP 설정
.env                →    env_file                  # 환경변수
```

### 배포 흐름
```
개선 에이전트 → QA 통과 → main 머지
  → docker compose build --no-cache
  → docker compose up -d
  → 헬스체크 (30초)
  → 성공: 텔레그램 알림
  → 실패: docker compose down → git revert → docker compose up -d → 텔레그램 알림
```

### Claude Code in Docker
- Claude Code CLI를 컨테이너 안에 설치
- `.claude/` 디렉토리를 호스트와 볼륨 공유 → 에이전트 프롬프트 수정이 컨테이너 재빌드 없이 반영
- MCP 서버(`mcp_server.py`)는 컨테이너 안에서 Claude Code가 subprocess로 실행
- Schedule trigger는 Claude Code cloud에서 실행 → MCP는 컨테이너 안의 서버에 연결

### invest.service (Docker host)
```ini
[Unit]
Description=fin-invest Docker Compose
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/bravopotato/Spaces/finspace/invest
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Key differences from DESIGN.md (the earlier simpler sketch): the earlier DESIGN.md describes a minimal prototype (just stock+polymarket, 4-hour reports, slash commands). This architecture is the full REQUIREMENTS.md system with multi-agent analysis, signal filtering, causal chain tracking, 3 portfolios, and autonomous operations.

---

## 2. Complete DB Schema

All tables in a single `invest.db` file, SQLite WAL mode.

```sql
-- ============================================================
-- PRAGMA settings (applied on every connection)
-- ============================================================
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

-- ============================================================
-- WATCHLISTS
-- ============================================================
CREATE TABLE IF NOT EXISTS watched_stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL UNIQUE,         -- '005930' (KR) or 'NVDA' (US)
    name TEXT,                           -- '삼성전자'
    market TEXT DEFAULT 'KOSPI',         -- KOSPI, KOSDAQ, NYSE, NASDAQ, etc.
    country TEXT DEFAULT 'KR',           -- 'KR', 'US', 'JP', 'EU' -- collector routing key
    reuters_code TEXT,                   -- 'NVDA.O' for Naver foreign chart API
    asset_type TEXT DEFAULT 'stock',     -- 'stock', 'etf', 'index'
    added_at TEXT DEFAULT (datetime('now','localtime')),
    active INTEGER DEFAULT 1
);
-- Collector routing: country='KR' → naver_stock.py (polling + integration + chart)
--                    country='US' → naver chart/foreign + yfinance_fallback (fundamentals)
--                    country='JP'/'EU' → naver chart/foreign only

CREATE TABLE IF NOT EXISTS watched_polymarkets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL UNIQUE,      -- Polymarket condition_id
    question TEXT,
    slug TEXT,
    category TEXT,                       -- 'politics', 'economics', 'geopolitics'
    end_date TEXT,
    linked_risk_id INTEGER,             -- FK to geopolitical_risks
    added_at TEXT DEFAULT (datetime('now','localtime')),
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS watched_crypto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,         -- 'BTC', 'ETH', 'XRP'
    name TEXT,                           -- '비트코인'
    exchange TEXT DEFAULT 'UPBIT',       -- 'UPBIT', 'BITHUMB'
    added_at TEXT DEFAULT (datetime('now','localtime')),
    active INTEGER DEFAULT 1
);

-- ============================================================
-- TIME SERIES DATA
-- ============================================================
CREATE TABLE IF NOT EXISTS stock_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,             -- ISO 8601 localtime
    ticker TEXT NOT NULL,
    source TEXT DEFAULT 'naver',         -- 'naver', 'naver_polling', 'yfinance', 'pykrx'
    price REAL,                          -- 현재가/종가
    open_price REAL,
    high REAL,
    low REAL,
    volume INTEGER,
    change_pct REAL,
    -- Korean stock extras (from Naver integration)
    market_cap TEXT,                     -- 시가총액 (formatted string)
    per REAL,
    pbr REAL,
    eps REAL,
    foreign_rate REAL,                   -- 외국인소진율
    foreign_net_buy INTEGER,             -- 외국인 순매수
    institution_net_buy INTEGER,         -- 기관 순매수
    individual_net_buy INTEGER,          -- 개인 순매수
    -- Interval marker
    interval TEXT DEFAULT 'realtime',    -- 'realtime', 'daily', 'weekly', 'monthly'
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
    price_krw REAL,                      -- KRW 시세
    price_usd REAL,                      -- USD 환산
    kimchi_premium REAL,                 -- 김치프리미엄 (%)
    change_pct REAL,
    volume REAL,
    market_cap REAL,
    UNIQUE(timestamp, symbol, exchange)
);

CREATE TABLE IF NOT EXISTS market_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    category TEXT NOT NULL,              -- 'index', 'fx', 'commodity', 'bond'
    code TEXT NOT NULL,                  -- 'KOSPI', 'FX_USDKRW', 'GCcv1', 'US10YT'
    name TEXT,
    value REAL,
    change_pct REAL,
    extra_json TEXT,                     -- JSON for additional fields
    UNIQUE(timestamp, category, code)
);

-- ============================================================
-- EVENTS CALENDAR
-- ============================================================
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_date TEXT NOT NULL,            -- YYYY-MM-DD
    event_time TEXT,                     -- HH:MM (KST)
    name TEXT NOT NULL,                  -- 'CPI (2월)', 'NVDA 실적'
    event_type TEXT NOT NULL,            -- 'economic', 'earnings', 'dividend', 'ipo',
                                        -- 'policy', 'option_expiry', 'polymarket'
    importance TEXT DEFAULT 'MED',       -- 'CRITICAL', 'HIGH', 'MED', 'LOW'
    affected_tickers TEXT,              -- JSON: ["NVDA", "005930"]
    affected_sectors TEXT,              -- JSON: ["IT", "반도체"]
    consensus TEXT,                      -- Expected value
    previous TEXT,                       -- Previous value
    actual TEXT,                         -- Filled after event
    surprise_pct REAL,                   -- actual vs consensus delta
    notes TEXT,
    activated_agents TEXT,              -- JSON: ["macro", "finance"]
    created_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(event_date, name)
);

-- ============================================================
-- SIGNAL QUALITY (7-filter results)
-- ============================================================
CREATE TABLE IF NOT EXISTS signal_quality (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    ticker TEXT NOT NULL,
    signal_type TEXT NOT NULL,           -- 'price_move', 'volume_spike', 'news',
                                        -- 'technical_breakout', 'polymarket_shift'
    raw_magnitude REAL,                  -- Raw signal strength
    volume_score REAL DEFAULT 1.0,       -- Filter 1: volume confirmation
    breadth_score REAL DEFAULT 1.0,      -- Filter 2: market breadth
    liquidity_score REAL DEFAULT 1.0,    -- Filter 3: liquidity/session
    dedup_score REAL DEFAULT 1.0,        -- Filter 4: news deduplication
    stophunt_score REAL DEFAULT 1.0,     -- Filter 5: stop hunting detection
    crossasset_score REAL DEFAULT 1.0,   -- Filter 6: cross-asset agreement
    historical_score REAL DEFAULT 1.0,   -- Filter 7: historical hit rate
    final_quality REAL,                  -- Product of all filter scores
    description TEXT,                    -- Human-readable signal description
    was_real INTEGER,                    -- Post-hoc: 1=real, 0=false, NULL=pending
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
    source TEXT,                         -- 'websearch', 'naver_news', 'finnhub'
    event_type TEXT,                     -- From half-life table categories
    magnitude REAL,                      -- Calculated impact magnitude
    surprise_factor REAL,
    regime_at_time TEXT,                 -- 'risk_on', 'risk_off', etc.
    half_life_hours REAL,               -- Regime-adjusted half-life
    decay_type TEXT DEFAULT 'exponential', -- 'exponential', 'step', 'dual', 'residual'
    affected_tickers TEXT,              -- JSON array
    expires_at TEXT,                     -- When residual < 12.5%
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS causal_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,           -- FK to news_events
    target_ticker TEXT NOT NULL,
    chain_depth INTEGER NOT NULL,        -- 1, 2, or 3
    magnitude_pct REAL NOT NULL,         -- Expected impact (%)
    delay_hours REAL DEFAULT 0,          -- Propagation delay
    half_life_hours REAL,
    confidence REAL NOT NULL,            -- This link's confidence (0-1)
    chain_confidence REAL NOT NULL,      -- Cumulative (product along chain)
    reasoning TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (event_id) REFERENCES news_events(id)
);

-- ============================================================
-- GEOPOLITICAL RISKS (Layer 2)
-- ============================================================
CREATE TABLE IF NOT EXISTS geopolitical_risks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                  -- '이란-이스라엘 분쟁'
    category TEXT NOT NULL,             -- 'war', 'political', 'trade', 'sanctions', 'social'
    status TEXT NOT NULL,                -- 'escalating', 'stable', 'de_escalating', 'resolved'
    severity INTEGER NOT NULL,           -- 1-10
    risk_premium_json TEXT,             -- {"WTI": +8.0, "gold": +3.0, ...}
    affected_assets TEXT,               -- JSON array
    safe_haven_boost REAL,
    scenarios_json TEXT,                -- [{"name":"확대","prob":0.30,"impact":{...}}, ...]
    escalation_prob REAL,
    resolution_prob REAL,
    polymarket_ids TEXT,                -- JSON: linked Polymarket event IDs
    started_at TEXT,
    last_updated TEXT DEFAULT (datetime('now','localtime')),
    resolved_at TEXT
);

-- ============================================================
-- MODEL PARAMETERS (tunable by improvement agent)
-- ============================================================
CREATE TABLE IF NOT EXISTS model_params (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,              -- 'half_life', 'impact_magnitude', 'regime',
                                        -- 'signal_filter', 'technical', 'position_sizing'
    param_name TEXT NOT NULL,            -- 'earnings_surprise_halflife_risk_on'
    value REAL NOT NULL,
    calibration_factor REAL DEFAULT 1.0,
    description TEXT,
    updated_by TEXT DEFAULT 'initial',   -- 'initial', 'improvement_agent', 'manual'
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(category, param_name)
);

-- ============================================================
-- PREDICTIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id TEXT NOT NULL,              -- '2026-03-30T16:00'
    agent_role TEXT NOT NULL,            -- 'leader', 'goguma', 'micro', etc.
    target_id TEXT NOT NULL,             -- '005930', 'NVDA', 'BTC'
    target_name TEXT,
    target_type TEXT NOT NULL,           -- 'stock', 'crypto', 'index', 'fx', 'commodity', 'bond', 'polymarket'

    -- Prediction content (probability distribution)
    predicted_direction TEXT,            -- 'up', 'down', 'stable'
    predicted_median_pct REAL,
    predicted_ci70_low REAL,
    predicted_ci70_high REAL,
    predicted_ci90_low REAL,
    predicted_ci90_high REAL,
    confidence INTEGER,                  -- 0-100
    reasoning TEXT,                      -- Factor decomposition + rationale

    -- Meta
    horizon TEXT NOT NULL,               -- '4h', '1d', '5d', '1m'
    baseline_price REAL NOT NULL,
    evaluation_at TEXT NOT NULL,
    status TEXT DEFAULT 'pending',       -- 'pending', 'evaluated', 'skipped'

    -- Verification results (filled later)
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
-- STRATEGY NOTES (per-agent learning)
-- ============================================================
CREATE TABLE IF NOT EXISTS strategy_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_role TEXT NOT NULL,
    content TEXT NOT NULL,
    valid_regime TEXT DEFAULT 'all',     -- 'risk_on', 'risk_off', 'all'
    created_at TEXT DEFAULT (datetime('now','localtime')),
    expires_at TEXT,                     -- Auto-expire (default 30 days)
    decay_confidence REAL DEFAULT 1.0,
    contradicted_count INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1            -- False when contradicted_count >= 3
);

-- ============================================================
-- AGENT ACCURACY TRACKING
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_accuracy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_role TEXT NOT NULL,
    period TEXT NOT NULL,                -- '2026-W13', '2026-03', '2026-Q1'
    regime TEXT,                         -- 'risk_on', 'risk_off', 'all'
    total_predictions INTEGER DEFAULT 0,
    direction_correct INTEGER DEFAULT 0,
    direction_rate REAL,
    avg_median_error REAL,
    ci70_hit_rate REAL,
    ci90_hit_rate REAL,
    calibration_score REAL,             -- How well confidence matches reality
    systematic_bias REAL,               -- Positive = bullish bias, negative = bearish
    ensemble_weight REAL DEFAULT 1.0,   -- Dynamic weight for leader's ensemble
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(agent_role, period, regime)
);

-- ============================================================
-- PORTFOLIOS
-- ============================================================
CREATE TABLE IF NOT EXISTS user_portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    name TEXT,
    qty REAL NOT NULL,
    avg_price REAL NOT NULL,
    currency TEXT DEFAULT 'KRW',
    sector TEXT,
    added_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(ticker)
);

CREATE TABLE IF NOT EXISTS user_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    ticker TEXT NOT NULL,
    name TEXT,
    action TEXT NOT NULL,                -- 'buy', 'sell'
    qty REAL NOT NULL,
    price REAL NOT NULL,
    currency TEXT DEFAULT 'KRW',
    note TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS user_cash (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    currency TEXT NOT NULL UNIQUE,       -- 'KRW', 'USD'
    amount REAL NOT NULL DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS goguma_portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    name TEXT,
    qty REAL NOT NULL,
    avg_price REAL NOT NULL,
    currency TEXT DEFAULT 'KRW',
    sector TEXT,
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(ticker)
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
    reasoning TEXT,                      -- Goguma's reasoning
    approved INTEGER DEFAULT 0,          -- 1 if user approved execution
    approved_at TEXT,
    execution_price REAL,                -- Actual price at approval time
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
    action TEXT NOT NULL,                -- 'buy', 'sell', 'hold', 'watch'
    target_price REAL,
    stop_loss REAL,
    confidence INTEGER,
    reasoning TEXT,
    followed INTEGER,                    -- Did user follow? 1/0/NULL
    outcome_pct REAL,                    -- What happened after recommendation
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    portfolio_type TEXT NOT NULL,         -- 'user', 'goguma', 'benchmark_kospi', 'benchmark_sp500'
    total_value_krw REAL,
    total_cost_krw REAL,
    total_pnl_krw REAL,
    total_pnl_pct REAL,
    cash_krw REAL,
    holdings_json TEXT,                  -- JSON snapshot of all positions
    fx_rates_json TEXT,                  -- FX rates at snapshot time
    created_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(timestamp, portfolio_type)
);

-- ============================================================
-- TELEGRAM CONTEXT
-- ============================================================
CREATE TABLE IF NOT EXISTS telegram_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER,                  -- Telegram message_id
    chat_id TEXT NOT NULL,
    role TEXT NOT NULL,                   -- 'user', 'bot'
    text TEXT NOT NULL,
    reply_to_message_id INTEGER,         -- If this is a reply
    intent TEXT,                          -- Classified intent
    context_type TEXT,                   -- 'report', 'alert', 'prediction', 'trade', etc.
    context_ref TEXT,                    -- Reference ID (report cycle_id, prediction id, etc.)
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- PENDING ACTIONS (Telegram confirmation flow)
-- ============================================================
CREATE TABLE IF NOT EXISTS pending_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL,
    action_type TEXT NOT NULL,          -- 'add_stock', 'remove_stock', 'goguma_trade', etc.
    params_json TEXT NOT NULL,          -- {"ticker": "005930", "name": "삼성전자", ...}
    description TEXT,                   -- Human-readable description shown to user
    status TEXT DEFAULT 'pending',      -- 'pending', 'approved', 'rejected', 'expired'
    created_at TEXT DEFAULT (datetime('now','localtime')),
    expires_at TEXT                     -- Auto-expire after 5 minutes
);

-- ============================================================
-- REPORTS LOG
-- ============================================================
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id TEXT NOT NULL,
    report_type TEXT NOT NULL,           -- 'tier3_full', 'tier2_alert', 'tier2_premarket'
    triggered_by TEXT,                   -- 'schedule', 'signal', 'user'
    agents_activated TEXT,              -- JSON: ["leader", "macro", "finance"]
    content_telegram TEXT,              -- Telegram-formatted summary
    content_notion_url TEXT,            -- Notion page URL
    duration_seconds INTEGER,
    notification_sent INTEGER DEFAULT 0, -- 1 after Telegram+Notion delivery confirmed
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- SYSTEM HEALTH
-- ============================================================
CREATE TABLE IF NOT EXISTS system_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    component TEXT NOT NULL,             -- 'collector_naver', 'collector_yfinance',
                                        -- 'telegram_bot', 'mcp_server', 'scheduler'
    status TEXT NOT NULL,                -- 'ok', 'warning', 'error', 'down'
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
    status TEXT,                         -- 'success', 'failed', 'rolled_back'
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
```

---

## 3. Python Daemon Design

### 3.1 main.py -- Entry Point

```python
# main.py -- Single-process asyncio event loop
async def main():
    # 1. Initialize DB (create tables, check integrity, WAL mode)
    db = Database("invest.db")

    # 2. Start components concurrently
    await asyncio.gather(
        run_telegram_bot(db),         # python-telegram-bot 22.x async
        run_scheduler(db),            # APScheduler AsyncIOScheduler
        run_health_monitor(db),       # Periodic health checks
    )
```

**MCP 서버는 별도 프로세스.** Claude Code가 `.claude/settings.local.json`에 등록된 MCP 서버를 subprocess로 직접 실행. main.py에 포함하지 않는다. `mcp_server.py`는 독립 실행 가능한 스크립트.

### 3.2 Data Collector Modules

`collectors/base.py` defines:
```python
class BaseCollector(ABC):
    def __init__(self, db: Database, config: Config):
        self.db = db
        self.session: aiohttp.ClientSession  # shared session
        self.error_count = 0
        self.cooldown_until: datetime | None = None

    async def collect(self) -> list[dict]:
        """Collect data. Returns list of records to insert."""
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return []
        try:
            data = await self._fetch()
            self.error_count = 0
            return data
        except Exception:
            self.error_count += 1
            if self.error_count >= 5:
                self.cooldown_until = datetime.now() + timedelta(minutes=30)
            return await self._fallback()

    @abstractmethod
    async def _fetch(self) -> list[dict]: ...

    async def _fallback(self) -> list[dict]:
        return []  # Override in subclasses
```

`collectors/naver_stock.py` -- Three collection modes:

1. **Polling (70s)**: `polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{code}` for real-time prices during market hours. The polling API returns `nv` (current price), `aq` (volume), `cr` (change %), and `pollingInterval: 70000`. This writes to `stock_prices` with `interval='realtime'`.

2. **Integration (on demand)**: `m.stock.naver.com/api/stock/{code}/integration` for full fundamentals (PER, PBR, investor flow, consensus). Called once when a stock is first added, and then once daily. Populates the extended columns of `stock_prices` and also updates `watched_stocks` metadata.

3. **Chart (daily)**: `api.stock.naver.com/chart/domestic/item/{code}?periodType=dayCandle` for daily OHLCV. On initial add, fetches max history (~110 trading days for day candle; use legacy `fchart.stock.naver.com` with `count=2500` for multi-year backfill). Writes to `stock_prices` with `interval='daily'`.

`collectors/naver_index.py`:
- Domestic: `polling...SERVICE_INDEX:KOSPI` (70s), `chart/domestic/index/KOSPI?periodType=dayCandle` (daily)
- Foreign: `api.stock.naver.com/index/nation/USA` (70s during US market hours) for DJI, IXIC, INX, SOX, VIX

On initial setup, backfill historical data for major indices using:
- Domestic: `api.stock.naver.com/chart/domestic/index/KOSPI?periodType=dayCandle` (max range)
- Foreign: `api.stock.naver.com/chart/foreign/index/.INX?periodType=dayCandle` (max range)
This is handled by `scripts/backfill_history.py` alongside stock backfill.

`collectors/naver_market.py`:
- FX: `front-api/marketIndex/exchange/main` (5 min)
- Commodities: `front-api/marketIndex/energy` + `metals` (5 min)
- Bonds: `front-api/marketIndex/bondList?countryCode=USA` + `KOR` (5 min)
- Crypto: `front-api/crypto/top?exchangeType=UPBIT` (5 min)
- All-in-one: `front-api/marketIndex/majors` (5 min)

`collectors/yfinance_fallback.py`:
- US stock fundamentals (PER, EPS, market cap): `yf.Ticker(t).info`
- Historical FX/commodity/bond/crypto OHLCV: `yf.download()`
- Called daily, or as fallback when Naver fails

`collectors/polymarket.py`:
- CLOB API for order book data, Gamma API for market metadata
- 5 min polling, 24/7
- Probability shift detection feeds into signal_detector

`collectors/upbit.py`:
- Upbit REST API for crypto OHLCV candles (historical backfill only)
- Called once on crypto watchlist addition (max history backfill)
- Ongoing 5-min realtime price: Naver `front-api/crypto/top` (in naver_market.py)
- Upbit is NOT called on 5-min schedule — only for historical OHLCV backfill

**Data gaps to address in Phase 3+:**
- Positioning (CFTC COT, 13F): No free real-time API. Design: agents use WebSearch to find latest COT reports. Manual entry via Telegram also supported.
- Options flow (call/put ratio): yfinance `options` attribute for major US tickers. Add to `yfinance_fallback.py`.
- Short interest: yfinance `info.shortPercentOfFloat` where available. Add to `yfinance_fallback.py`.
- Cross-asset correlation: Computed by `engine/technical.py` on demand from stored price data. No separate table needed — calculated live from `stock_prices` + `market_indicators`.

### 3.3 Signal Detector

`engine/signal_detector.py` runs after each collection cycle:

```python
async def detect_signals(db: Database, new_data: list[dict]) -> list[Signal]:
    signals = []
    for record in new_data:
        # Price move detection: Z-score vs 20-period rolling mean/std
        if abs(record.change_pct) > threshold:
            signals.append(Signal(type='price_move', ...))
        # Volume spike: current volume vs 20-period average
        if record.volume > avg_volume * 2.0:
            signals.append(Signal(type='volume_spike', ...))
        # Polymarket probability shift: >5pp in 1 hour
        # Technical breakout: price crossing key MA levels
    return signals
```

Each detected signal then passes through `engine/signal_filter.py` (the 7-filter pipeline). Each filter returns a score 0.0-1.0; the final quality is the product. Signals with `final_quality >= 0.7` trigger Tier 2 alerts; `0.4-0.7` are logged but not alerted; `< 0.4` are discarded.

`engine/prediction_evaluator.py` also handles accuracy aggregation:
After evaluating individual predictions, it aggregates results into `agent_accuracy` table:
- Groups evaluated predictions by (agent_role, ISO week, regime)
- Calculates direction_rate, avg_median_error, ci70_hit_rate, ci90_hit_rate
- Computes calibration_score: correlation between confidence and actual hit rate
- Detects systematic_bias: mean signed error (positive = bullish bias)
- Updates ensemble_weight based on recent accuracy
This runs as part of the hourly `evaluate_predictions` scheduler job.

### 3.4 Impact Calculator (3-Layer Model)

`engine/impact_calculator.py`:
```python
def get_total_impact(db: Database, ticker: str, now: datetime) -> TotalImpact:
    # Layer 1: Sum of active news event residuals
    layer1 = sum_event_residuals(db, ticker, now)

    # Layer 2: Geopolitical risk premiums
    layer2 = sum_risk_premiums(db, ticker)

    # Layer 3: Polymarket probability adjustments
    layer3 = polymarket_adjustment(db, ticker)

    return TotalImpact(
        layer1=layer1, layer2=layer2, layer3=layer3,
        total=layer1 + layer2 + layer3
    )
```

`engine/decay_engine.py` implements the four decay types:
- **Exponential**: `magnitude * exp(-0.693 * elapsed / half_life) * confidence`
- **Step**: Full value until trigger date, then rapid decay
- **Dual**: 30% decays fast (half_life/3), 70% decays at full half_life
- **Residual**: Exponential decay + fixed residual percentage

### 3.5 Technical Indicator Engine

`engine/technical.py` calculates from stored OHLCV data:
- SMA (20, 50, 100, 200), EMA
- RSI (14)
- MACD (12, 26, 9)
- Bollinger Bands (20, 2)
- Fibonacci retracement/extension
- ATR (14) for volatility-based stops
- Volume profile (price-level clustering)
- Pivot points

These are computed on demand (when an agent queries via MCP) rather than pre-stored, since they derive from the stored OHLCV.

### 3.6 Regime Detector

`engine/regime_detector.py`:
```python
def detect_regime(db: Database) -> Regime:
    vix = get_latest_indicator(db, 'index', '.VIX')
    # HY spread: from yfinance or manual input
    breadth = calculate_breadth(db)  # advance/decline from ETF data
    safe_haven = calculate_safe_haven_flow(db)  # gold, yen, treasury

    score = (
        vix_score(vix) * 0.35
        + spread_score(hy_spread) * 0.25
        + breadth_score(breadth) * 0.20
        + flow_score(safe_haven) * 0.20
    )

    if score > 0.7: return Regime.RISK_ON
    if score > 0.4: return Regime.TRANSITION
    if score > 0.15: return Regime.RISK_OFF
    return Regime.CRISIS
```

Thresholds are read from `model_params` table, so the improvement agent can tune them without code changes.

### 3.7 Telegram Bot

`bot/telegram.py` uses `python-telegram-bot` 22.x with async handlers:

```python
from telegram.ext import ApplicationBuilder, MessageHandler, filters

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = str(update.effective_chat.id)
    reply_to = update.message.reply_to_message

    # Save incoming message to DB
    save_message(db, message_id=update.message.message_id,
                 chat_id=chat_id, role='user', text=text,
                 reply_to=reply_to.message_id if reply_to else None)

    # Stage 1: Fast keyword matching (Python, instant)
    intent, response = classify_stage1(text, reply_to)
    if response:
        sent = await update.message.reply_text(response, parse_mode='Markdown')
        save_message(db, message_id=sent.message_id, chat_id=chat_id,
                     role='bot', text=response)
        return

    # Stage 2: Claude Code for complex intents
    # Send intermediate "analyzing" message
    thinking_msg = await update.message.reply_text("🔍 분석 중...")

    response = await asyncio.to_thread(
        call_claude_for_intent, text, chat_id, reply_to, intent
    )

    # Delete thinking message and send real response
    await thinking_msg.delete()
    sent = await update.message.reply_text(response, parse_mode='Markdown')
    save_message(db, message_id=sent.message_id, chat_id=chat_id,
                 role='bot', text=response)
```

### 3.8 MCP Server

**Performance note:** `mcp_server.py` is spawned fresh by Claude Code on every invocation.
Keep module-level imports minimal. Heavy libraries (pandas, numpy) should use lazy imports:
```python
def get_technical(ticker: str) -> str:
    import pandas as pd  # lazy import, only when this tool is called
    ...
```

`mcp_server.py` using `FastMCP`:

```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("fin-invest")

@mcp.tool()
def get_price(ticker: str) -> str: ...

@mcp.tool()
def get_chart(ticker: str, period: str = "6m", interval: str = "daily") -> str: ...

@mcp.tool()
def get_fundamentals(ticker: str) -> str: ...

@mcp.tool()
def get_investor_flow(ticker: str) -> str: ...

@mcp.tool()
def get_crypto(symbol: str) -> str: ...

@mcp.tool()
def get_polymarket(market_id: str) -> str: ...

@mcp.tool()
def get_indices() -> str: ...

@mcp.tool()
def get_active_impacts(ticker: str) -> str: ...

@mcp.tool()
def get_causal_chain(ticker: str = "", event_type: str = "") -> str:
    """Get active causal chains. Filter by ticker and/or event_type."""
    ...

@mcp.tool()
def get_geopolitical_risks() -> str: ...

@mcp.tool()
def get_signal_quality(ticker: str) -> str: ...

@mcp.tool()
def get_events(days_ahead: int = 7) -> str: ...

@mcp.tool()
def get_regime() -> str: ...

@mcp.tool()
def get_predictions(agent: str = "", status: str = "pending") -> str: ...

@mcp.tool()
def get_accuracy(agent: str = "", period: str = "") -> str: ...

@mcp.tool()
def get_strategy_notes(agent: str) -> str: ...

@mcp.tool()
def get_portfolio(portfolio_type: str = "user") -> str: ...

@mcp.tool()
def record_trade(ticker: str, action: str, qty: float, price: float,
                 currency: str = "KRW") -> str: ...

@mcp.tool()
def execute_virtual_trade(ticker: str, action: str, amount: float,
                          reasoning: str = "") -> str: ...

@mcp.tool()
def compare_portfolios() -> str: ...

@mcp.tool()
def get_technical(ticker: str) -> str: ...

@mcp.tool()
def get_watchlist() -> str: ...

@mcp.tool()
def save_prediction(agent_role: str, target_id: str, horizon: str,
                    direction: str, median_pct: float, confidence: int,
                    ci70_low: float, ci70_high: float,
                    ci90_low: float, ci90_high: float,
                    reasoning: str) -> str: ...

@mcp.tool()
def save_causal_link(headline: str, event_type: str, target_ticker: str,
                     chain_depth: int, magnitude_pct: float,
                     confidence: float, reasoning: str) -> str: ...

@mcp.tool()
def update_geopolitical_risk(name: str, status: str, severity: int,
                              risk_premium_json: str,
                              escalation_prob: float,
                              resolution_prob: float) -> str: ...

@mcp.tool()
def save_report(cycle_id: str, report_type: str, content_telegram: str,
                agents_activated: str, duration_seconds: int) -> str:
    """Save report to DB. Python health monitor detects new reports and sends to Telegram/Notion."""
    ...

@mcp.tool()
def update_portfolio_snapshot(portfolio_type: str, holdings_json: str,
                               cash_json: str) -> str:
    """Replace entire portfolio with snapshot. For when user sends full holdings at once."""
    ...

@mcp.tool()
def update_model_param(category: str, param_name: str, value: float,
                       updated_by: str = "improvement_agent") -> str:
    """Update a model parameter. Used by improvement agent for tuning."""
    ...

@mcp.tool()
def save_strategy_note(agent_role: str, content: str,
                       valid_regime: str = "all") -> str:
    """Save a strategy note for an agent. Auto-expires in 30 days."""
    ...

@mcp.tool()
def add_stock(ticker: str, name: str, market: str, country: str = "KR") -> str:
    """Add stock to watchlist and trigger historical backfill."""
    ...

@mcp.tool()
def remove_stock(ticker: str) -> str:
    """Deactivate stock from watchlist (soft delete)."""
    ...

@mcp.tool()
def add_crypto(symbol: str, name: str, exchange: str = "UPBIT") -> str:
    """Add crypto to watchlist."""
    ...

@mcp.tool()
def add_polymarket(market_id: str, question: str, category: str = "") -> str:
    """Add Polymarket event to watchlist."""
    ...

@mcp.tool()
def get_market_data(category: str = "") -> str:
    """Get FX, commodities, bonds data from market_indicators. Optional category filter."""
    ...
```

Registration in `.claude/settings.local.json`:
```json
{
  "permissions": {
    "allow": [
      "mcp__fin-invest__*"
    ]
  },
  "mcpServers": {
    "fin-invest": {
      "command": "/home/bravopotato/Spaces/finspace/invest/.venv/bin/python3",
      "args": ["/home/bravopotato/Spaces/finspace/invest/mcp_server.py"],
      "cwd": "/home/bravopotato/Spaces/finspace/invest"
    }
  }
}
```

### 3.9 Scheduler

`scheduler/jobs.py` using APScheduler `AsyncIOScheduler`:

| Job | Interval | Condition |
|-----|----------|-----------|
| `collect_kr_stocks` | 70s | Weekday 08:55-15:35 KST |
| `collect_kr_indices` | 70s | Weekday 08:55-15:35 KST |
| `collect_us_indices` | 70s | Mon-Fri 22:30-05:00+1 KST |
| `collect_fx_commodities_bonds` | 5 min | Always |
| `collect_crypto` | 5 min | Always (24/7) |
| `collect_polymarket` | 5 min | Always (24/7) |
| `collect_daily_chart` | daily 06:00 | Once per day |
| `collect_us_fundamentals` | daily 06:00 | Once per day |
| `detect_signals` | After each collect | Always |
| `evaluate_predictions` | 1 hour | Always |
| `check_event_calendar` | 1 hour | Always (D-7/3/1/0 alerts) |
| `health_check` | 5 min | Always |
| `db_backup` | daily 04:00 | Always |
| `db_compress` | daily 04:30 | Always (90-day minute data) |
| `trigger_tier3_report` | See 9.5 | Schedule triggers |
| `trigger_tier3_periodic` | 4 hours | During market hours (KST 09:00-05:00+1) |
| `portfolio_snapshot` | daily 15:36 KST, 05:01 KST | Market close times |

---

## 4. Claude Code Integration

### 4.1 How Python Triggers Claude Code

Two mechanisms:

**A. subprocess call (for Telegram NLU and on-demand analysis):**
```python
# bot/claude_bridge.py
CLAUDE_PATH = "/home/linuxbrew/.linuxbrew/bin/claude"

# Limit concurrent Claude Code invocations to prevent resource exhaustion
_claude_semaphore = asyncio.Semaphore(3)  # max 3 concurrent processes

async def call_claude_async(prompt: str, **kwargs) -> str:
    async with _claude_semaphore:
        return await asyncio.to_thread(call_claude, prompt, **kwargs)

# Agent-specific model overrides
AGENT_MODELS = {
    "leader": "opus",
    "goguma": "opus",
}

def call_claude(prompt: str, model: str = "sonnet",
                allowed_tools: str = "mcp__fin-invest__*,WebSearch",
                agent: str = "") -> str:
    # Override model for specific agents
    if agent and agent in AGENT_MODELS:
        model = AGENT_MODELS[agent]
    cmd = [CLAUDE_PATH, '-p', prompt,
           '--model', model,
           '--allowedTools', allowed_tools]
    if agent:
        cmd += ['--agent', agent]
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        timeout=300,
        cwd="/home/bravopotato/Spaces/finspace/invest",
        env={**os.environ}
    )
    return result.stdout.strip()
```

**B. Schedule triggers (for periodic reports):**

Using Claude Code's built-in schedule trigger system (the `/schedule` skill). This is the cleanest integration -- no cron, no shell scripts. The schedule trigger creates a remote Claude Code agent that runs on a cron schedule, with a prompt and full access to MCP tools and subagents.

Configuration for periodic reports:
```
# Created via `claude /schedule create`:
Schedule: "Tier 3 Report - US Market Close"
  Cron: "5 5 * * 2-6"   # 05:05 KST Tue-Sat (after US close)
  Prompt: "Run a full Tier 3 analysis report. Read CLAUDE.md for instructions.
           Use the leader agent to orchestrate..."

Schedule: "Tier 3 Report - Korea Market Close"
  Cron: "40 15 * * 1-5"  # 15:40 KST Mon-Fri
  Prompt: "Run Korean market close report..."

Schedule: "Tier 3 Report - Periodic 4h"
  Cron: "0 */4 * * *"    # Every 4 hours
  Prompt: "Run periodic Tier 3 report..."

Schedule: "Daily Improvement Cycle"
  Cron: "0 6 * * *"      # 06:00 KST daily
  Prompt: "Run the improvement agent cycle..."
```

**C. Python-initiated report trigger (for Tier 2 alerts):**

When the signal detector finds a high-quality signal (`final_quality >= 0.7`), Python calls `call_claude()` with the appropriate agent prompt to generate an urgent analysis.

### 4.2 Subagent Definitions

All 12 agents live in `.claude/agents/`. Here are the key ones:

**`.claude/agents/leader.md`:**
```markdown
# Leader Agent -- 투자 분석 총괄

## Role
You are the lead investment analyst orchestrating a team of domain experts.
You make final calls on regime, strategy, and recommendations.

## Process
1. Query regime: use `get_regime()` MCP tool
2. Query active signals: `get_signal_quality()` for all watched tickers
3. Decide which experts to activate based on current conditions:
   - Always active: yourself + goguma (goguma runs independently in parallel)
   - Conditional: check events, signals, market hours
4. Launch selected experts as subagents (Task tool)
5. Collect expert analyses
6. Synthesize with Extended Thinking:
   - Cross-validate expert views
   - Build causal chains: `save_causal_link()` for new connections
   - Generate predictions: `save_prediction()` with probability distributions
   - Use `get_strategy_notes("leader")` to recall past learnings
7. Produce final report in Korean

## MCP Tools Available
[All tools from fin-invest MCP server]

## Output Format
Korean language report following the structure in CLAUDE.md Section 7.2.

## Rules
- NEVER make point predictions. Always probability distributions.
- If signal quality < 0.4, skip that signal entirely.
- If no edge exists for a ticker, say "엣지 없음" and do not predict.
- Weight expert opinions by their accuracy: `get_accuracy(agent)`.
- Use Extended Thinking for synthesis -- do not rush the final judgment.
```

**`.claude/agents/goguma.md`:**
```markdown
# 고구마 -- 독립 투자 개인비서

## Character
You are 고구마, an independent investment advisor.
- 반말 사용. 직설적, 현실적, 독설가.
- "솔직히 말해서...", "이건 좀 아닌데...", "너 이거 왜 샀어?"
- Analysis paralysis에 대한 해독제. 결정을 내려라.
- 사용자의 감정에 공감하되, 투자 판단은 냉정하게.

## CRITICAL RULES
- 팀 분석(leader, experts)의 결과를 절대 보지 않는다.
  당신은 독립적으로 분석한다. 앵커링 방지.
- MCP 도구만 사용하여 raw data를 직접 분석한다.
- WebSearch를 적극 활용하여 독자적으로 뉴스를 수집한다.

## Portfolio
- 1억원 현금으로 시작. 초기 종목 없음.
- `get_portfolio("goguma")`로 현재 상태 확인.
- 매매 시 `execute_virtual_trade()`로 기록.
- 매매 실행 가격은 사용자 수락 시점의 실시간 시세로 재계산됨 (제안 시점 가격 아님).

## Each Cycle
1. Check portfolio: `get_portfolio("goguma")`
2. Check market: `get_regime()`, `get_indices()`, `get_signal_quality()`
3. Research independently: WebSearch for news
4. Decide: buy/sell/hold for each position + new opportunities
5. Self-reflection: Review past recommendations via `get_accuracy("goguma")`
6. Apply `get_strategy_notes("goguma")` learnings
7. Compare vs benchmarks: `compare_portfolios()`

## Output
- Current portfolio status + P&L
- New trade proposals (if any): ticker, amount, direction, reasoning
- Self-reflection on recent calls
- One piece of unsolicited advice for the user (독설 포함)
- All in Korean, 반말
```

**`.claude/agents/macro-expert.md`** (representative domain expert):
```markdown
# Macro Expert -- 거시경제 전문가

## Role
Analyze macroeconomic conditions and their market implications.

## Domain
- Interest rates, inflation (CPI/PPI/PCE), GDP, employment
- Central bank policy (Fed, BOK, BOJ, ECB)
- Treasury yields, yield curve
- Monetary conditions, liquidity

## Process
1. Get latest data: `get_indices()`, check bond yields
2. WebSearch for latest economic data releases and Fed commentary
3. Get upcoming events: `get_events(7)` -- filter for economic events
4. Get active causal chains: `get_causal_chain()` for macro-related
5. Get strategy notes: `get_strategy_notes("macro")`
6. Analyze:
   - Current macro regime assessment
   - Key data points and their implications
   - Causal chains from macro events to portfolio assets
   - Confidence-weighted impact estimates
7. Return structured analysis in Korean

## Output Format
- 현재 거시 레짐: [assessment]
- 주요 지표: [table of latest readings]
- 인과 사슬: [event -> 1st -> 2nd order effects]
- 영향 종목: [which portfolio assets are affected, how]
- 확신도: [0-100]
```

The other 6 domain experts follow the same structure with their specific domain focus.

**`.claude/agents/improvement.md`:**
```markdown
# Improvement Agent -- 시스템 개선

## Role
Analyze system performance and make targeted improvements.

## Input Data (query via MCP)
- Prediction accuracy by agent: `get_accuracy()`
- Signal filter performance: query signal_quality where was_real is set
- Model params and calibration factors: `get_strategy_notes()`
- Error patterns from recent predictions

## Allowed Changes (max 3 per cycle)
- Agent prompts: .claude/agents/*.md
- Signal filter parameters in model_params table
- Technical indicator parameters in model_params table
- Half-life/impact defaults in model_params table
- Regime detection thresholds in model_params table
- Anomaly detection thresholds

## Forbidden
- DB schema changes
- MCP server core logic
- .env or authentication
- config.py core settings

## Workflow
1. Analyze accuracy data
2. Identify top 3 issues (by impact)
3. For each issue:
   a. Diagnose root cause
   b. Propose specific change
   c. Implement change (edit file or update model_params)
4. Create improve/YYYYMMDD branch
5. Hand off to QA agent
```

### 4.3 Report Cycle Orchestration

`scheduler/report_orchestrator.py` handles the preparation before a Claude Code report cycle:

```python
async def prepare_tier3_report(db: Database) -> dict:
    """Prepare all data that agents will need, ensure DB is fresh."""
    # 1. Run final data collection
    await collect_all_latest(db)

    # 2. Evaluate any expired predictions
    await evaluate_expired_predictions(db)

    # 3. Calculate regime
    regime = detect_regime(db)

    # 4. Get active signals with quality scores
    signals = get_active_signals(db)

    # 5. Determine which experts to activate
    experts = determine_active_experts(regime, signals, get_upcoming_events(db))

    # 6. Store preparation metadata
    cycle_id = datetime.now().strftime('%Y-%m-%dT%H:%M')
    db.insert('reports', cycle_id=cycle_id, report_type='tier3_full',
              agents_activated=json.dumps(experts))

    return {'cycle_id': cycle_id, 'regime': regime, 'experts': experts}
```

When triggered by a schedule trigger, the leader agent:
1. Reads `CLAUDE.md` to understand the full system
2. Calls MCP tools to get prepared data
3. Launches domain experts as subagents (using Task tool) in parallel
4. Launches goguma as a separate parallel subagent
5. Collects all results
6. Synthesizes with Extended Thinking
7. Leader calls `save_report()` MCP tool to persist the report to DB
8. Python's health monitor polls `reports` table (10s interval), detects new report, pushes to Telegram (summary) + Notion (full)

**CRITICAL: Goguma runs as a SEPARATE top-level Claude Code invocation, NOT as a subagent of the leader.**
The report orchestrator in Python launches two parallel subprocess calls:
1. `call_claude(prompt, agent="leader")` -- leader orchestrates experts
2. `call_claude(prompt, agent="goguma")` -- goguma runs independently
This ensures no context leakage from leader/experts to goguma. The Python process merges both results into the final report.

### 4.4 Telegram -> Claude Code -> Telegram Flow

This is the critical path for user messages:

```
User sends message via Telegram
    |
    v
python-telegram-bot receives update (async)
    |
    v
Save to telegram_messages table
    |
    v
Stage 1: intent_classifier.py (Python, instant)
    |-- Simple intents (price query, list, etc.) -> handle locally -> respond
    |-- Confirmation ("ㅇㅇ", "해줘") -> check pending_action -> execute -> respond
    |-- Complex intent detected -> Stage 2
    v
Stage 2: claude_bridge.py (subprocess, 10-90s)
    |
    v
Build prompt with:
    - User message
    - Recent conversation context (last 10 messages from telegram_messages)
    - Reply context (if reply, fetch the original message + its context_type)
    - Pending actions (if any)
    |
    v
Choose execution path:
    A. General question -> call_claude(prompt, model="sonnet", agent="")
    B. "고구마야..." -> call_claude(prompt, agent="goguma")
    C. "보고서 생성" -> call_claude(prompt, agent="leader")
    D. Analysis question -> call_claude(prompt, model="sonnet", uses MCP tools)
    |
    v
Claude Code runs with MCP tools, returns text response
    |
    v
Save bot response to telegram_messages (with context_type, context_ref)
    |
    v
Send to Telegram (with Markdown formatting, chunk if >4096 chars)
```

### 4.5 Context Manager Details

`bot/context_manager.py`:

```python
def build_context(db, chat_id: str, current_text: str,
                  reply_to_message_id: int | None) -> str:
    """Build conversation context for Claude."""
    parts = []

    # 1. If this is a reply, fetch the original message and its context
    if reply_to_message_id:
        original = db.get_message_by_id(reply_to_message_id)
        if original:
            parts.append(f"[사용자가 다음 메시지에 reply함]\n{original.text}")
            if original.context_type == 'report':
                # Fetch report summary
                report = db.get_report(original.context_ref)
                parts.append(f"[관련 보고서 요약]\n{report.content_telegram[:2000]}")
            elif original.context_type == 'alert':
                # Fetch signal details
                signal = db.get_signal(original.context_ref)
                parts.append(f"[관련 신호]\n{format_signal(signal)}")

    # 2. Recent conversation (last 10 messages)
    recent = db.get_recent_messages(chat_id, limit=10)
    if recent:
        parts.append("[최근 대화]")
        for msg in recent:
            role = '사용자' if msg.role == 'user' else '봇'
            parts.append(f"{role}: {msg.text[:200]}")

    # 3. Pending actions
    pending = db.get_pending_action(chat_id)
    if pending:
        parts.append(f"[대기 중인 액션: {pending.description}]")

    return '\n---\n'.join(parts)
```

---

## 5. Telegram Message Flow (Detailed)

### 5.1 Stage 1 Intent Classification

`bot/intent_classifier.py` handles patterns that do not need Claude:

| Pattern | Action |
|---------|--------|
| Ticker/name mention ("삼전", "NVDA") | Query MCP `get_price()`, respond |
| "목록", "뭐 보고 있어" | Query DB watched_stocks, respond |
| "시스템 상태" | Query system_health table, respond |
| "ㅇㅇ", "응", "해줘", "그래" | Execute pending_action (if any) |
| "아니", "취소", "ㄴㄴ" | Cancel pending_action |
| "고구마 포폴" | Query `get_portfolio("goguma")`, respond |
| Price alerts ("알림 설정") | DB operation |

### 5.2 Stage 2: Claude Code Processing

For anything that requires understanding, reasoning, or analysis:
- "지금 반도체 섹터 전체적으로 어떻게 보여?"
- "삼전 왜 올라?"
- Reply to a report message: "더 자세히"
- "고구마야, 내 포폴 너무 IT에 쏠려있지 않아?"
- "이번 주 FOMC 영향 어떻게 봐?"
- Portfolio snapshot from screenshot (image handling)

**Screenshot/Image handling:**
When the user sends an image (photo) via Telegram:
1. python-telegram-bot downloads the image to a temp file
2. The image path is passed to Claude Code: `claude -p "이 증권사 스크린샷에서 보유 종목과 수량을 추출해줘" --image /tmp/screenshot.jpg`
3. Claude Code (multimodal) reads the image, extracts holdings
4. Returns structured data → Python updates user_portfolio via MCP

### 5.3 Action Confirmation Pattern

Any action that modifies state requires confirmation:

```
User: "삼성전자 추가해줘"
[Stage 1 detects "추가" + stock name -> creates pending_action]
Bot: "삼성전자(005930)를 감시 목록에 추가하겠습니다.
      과거 일봉 데이터(~2년)도 함께 수집합니다.
      진행할까요?"
[pending_action stored in DB: {type: 'add_stock', ticker: '005930', ...}]

User: "ㅇㅇ"
[Stage 1 detects confirmation -> executes pending_action]
Bot: "추가 완료. 과거 데이터 수집 시작합니다. (예상 30초)"
[Background: backfill_history runs for 005930]
Bot: "삼성전자 과거 2년 일봉 데이터 수집 완료 (489일)"
```

### 5.4 Goguma Trade Flow

```
[Report cycle produces goguma trade proposal]
Bot: "🍠 고구마 매매 제안
      삼성전자(005930) 500만원 매수
      이유: 외국인 3일 연속 순매수, PBR 1.2배 역사적 하단
      현재가: ₩54,200

      실행할까요?"
[pending_action: {type: 'goguma_trade', ...}]

User: "ㅇㅇ"
[Get real-time price at THIS moment, not proposal time]
Bot: "고구마 매매 실행 완료.
      삼성전자 92주 × ₩54,350 = ₩5,000,200
      (제안 시점 ₩54,200 → 실행 시점 ₩54,350, +0.28%)
      고구마 잔여 현금: ₩94,999,800"
```

---

## 6. Notion Integration

### 6.1 What Goes Where

| Content | Telegram | Notion |
|---------|----------|--------|
| Tier 2 alerts | Full alert text (immediate) | Logged in alerts database |
| Tier 3 reports | Summary (2000 chars) with link to Notion | Full report (all sections) |
| Portfolio dashboard | On-demand query response | Always-updated database |
| Accuracy dashboard | On-demand query response | Always-updated database with charts |
| System health | Critical alerts only | Full status page |
| Goguma portfolio | Trade proposals + approvals | Full trade history + reasoning |
| Improvement logs | Summary of changes | Full diff + QA results |

### 6.2 Notion Page Structure

```
📊 fin-invest
├── 📄 Latest Report (always shows most recent Tier 3)
├── 📁 Reports Archive
│   ├── 2026-03-30 05:05 US Market Close
│   ├── 2026-03-29 15:40 Korea Market Close
│   └── ...
├── 📊 Dashboards
│   ├── Portfolio Comparison (user vs goguma vs benchmarks)
│   │   [Database: date, user_value, user_pnl%, goguma_value, goguma_pnl%,
│   │    kospi%, sp500%]
│   ├── Agent Accuracy Leaderboard
│   │   [Database: agent, period, direction_rate, calibration, weight]
│   ├── Signal Quality Tracker
│   │   [Database: date, total_signals, false_rate, avg_quality]
│   └── System Health
│       [Database: component, status, last_success, error_count]
├── 📁 Causal Chain Tracker
│   ├── Active Events Map (visual)
│   └── Geopolitical Risk Register
├── 📁 Goguma Corner
│   ├── Portfolio Status
│   ├── Trade History (with reasoning)
│   └── Performance vs Benchmarks
└── 📁 Improvement Log
    ├── Change History
    └── Parameter Tuning Record
```

### 6.3 Publishing Flow

`notion/report_publisher.py` is called after each Tier 3 report completes:

```python
async def publish_report(report_content: str, cycle_id: str):
    # 1. Create new page under Reports Archive
    page = await notion.create_page(
        parent_id=REPORTS_DB_ID,
        title=f"{cycle_id} Report",
        content=report_content  # Full markdown
    )

    # 2. Update "Latest Report" page to point to new report
    await notion.update_page(LATEST_REPORT_ID, content=report_content)

    # 3. Update dashboard databases
    await update_portfolio_dashboard(cycle_id)
    await update_accuracy_dashboard(cycle_id)

    return page.url
```

---

## 7. Operations Team Design

### 7.1 Improvement Agent Workflow (Daily at 06:00 KST)

Triggered by schedule trigger. The improvement agent (`.claude/agents/improvement.md`) runs as a Claude Code subagent:

1. **Data Collection Phase** (via MCP):
   - `get_accuracy("", "")` -- all agents, recent period
   - Query `signal_quality` for `was_real` vs `final_quality` correlation
   - Query `model_params` for current calibration factors
   - Query `predictions` for systematic errors (bias by direction, regime, ticker)

2. **Analysis Phase**:
   - Identify top 3 issues by impact on portfolio P&L
   - Examples:
     - "Macro expert has 12% bullish bias in risk-off regime"
     - "Signal filter's volume threshold too permissive (25% false positive rate)"
     - "Half-life for earnings_surprise is 40% too long in risk-on"

3. **Implementation Phase** (max 3 changes):
   - Create git branch `improve/20260330`
   - Edit agent prompts or update `model_params` via MCP
   - Each change logged with before/after values

4. **Handoff to QA**:
   - QA agent runs as subagent within same session
   - QA checks: `py_compile`, `bash -n`, logic review, regression check
   - If QA passes: auto-merge to main, `systemctl restart invest`, Telegram notification
   - If QA fails: branch deleted, Telegram failure notification

### 7.2 QA Agent Checks

The QA agent (`.claude/agents/qa.md`) performs:
- `python3 -m py_compile` on all changed `.py` files
- `bash -n` on all changed `.sh` files
- Run `pytest tests/` to check for regressions
- Review diff for dangerous patterns (hardcoded secrets, infinite loops, removed safety checks)
- Verify agent prompt changes are coherent and self-consistent

### 7.3 DevOps Agent

The DevOps agent (`.claude/agents/devops.md`) handles:
- **Git operations**: branch create, merge, tag, rollback
- **DB maintenance**: backup (daily compressed), integrity check, 90-day compression
- **Deploy**: `systemctl restart invest`, health check (30s), rollback if unhealthy
- **Monitoring**: Weekly DB status report to Telegram

### 7.4 Autonomous Recovery Flows

```
Process crash
    -> systemd Restart=always (immediate)
    -> If crash loops (>3 in 5 min): Telegram alert

Naver API failure
    -> error_count++ in BaseCollector
    -> 5 consecutive failures -> 30-min cooldown + yfinance/pykrx fallback
    -> Telegram alert: "네이버 API 장애, fallback 활성화"
    -> Cooldown expires -> retry Naver -> if works, restore primary

Deploy failure
    -> Health check fails within 30s
    -> git revert HEAD -> systemctl restart invest
    -> Telegram: "배포 실패, 자동 롤백 완료"

DB corruption
    -> Daily integrity_check detects issue
    -> Restore from latest backup
    -> Telegram alert
```

---

## 8. Test Strategy

### 8.1 Test Levels

| Level | 대상 | 방법 |
|-------|------|------|
| **Unit** | signal_filter, decay_engine, technical, regime_detector | pytest, 순수 함수 테스트 |
| **Integration** | collectors, db CRUD, impact_calculator | pytest + SQLite in-memory DB |
| **API Mock** | naver_stock, naver_market, polymarket | aioresponses로 HTTP 응답 모킹 |
| **E2E** | 텔레그램 메시지 → 응답, 보고서 생성 | 수동 (Phase별 검증에서 커버) |

### 8.2 Fixture Strategy

- `tests/fixtures/naver_stock_basic.json` — 네이버 주식 basic API 응답 샘플
- `tests/fixtures/naver_polling.json` — 네이버 폴링 API 응답 샘플
- `tests/fixtures/polymarket_market.json` — 폴리마켓 마켓 응답 샘플
- Phase 1에서 실제 API 응답을 캡처하여 fixture로 저장

### 8.3 CI

- `pytest tests/` — PR merge 전 QA 에이전트가 실행
- py_compile 전체 파일 — 구문 오류 검사
- 커버리지 목표: engine/ 80%+, collectors/ 60%+ (API 의존 부분은 mock)

---

## 9. Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
**Goal: Running daemon that collects data and stores it.**

Files to create:
- `config.py` -- Settings, env loading
- `db.py` -- Full schema creation, connection management
- `main.py` -- Basic asyncio entry point
- `collectors/base.py` -- BaseCollector with retry/fallback
- `collectors/naver_stock.py` -- Korean stock polling + chart
- `collectors/naver_market.py` -- FX, commodities, bonds (front-api/majors)
- `scheduler/jobs.py` -- Basic APScheduler with collection jobs
- `requirements.txt` -- aiohttp, apscheduler, python-telegram-bot
- `scripts/init_db.py` -- Schema init + seed model_params
- `.gitignore`, `.env`

**Validation**: Run `main.py`, verify `stock_prices` and `market_indicators` tables populate.

### Phase 2: Telegram Bot + MCP Server (Week 2)
**Goal: Basic Telegram interaction + Claude Code can query data.**

Files to create:
- `bot/telegram.py` -- Async Telegram bot with basic message handling
- `bot/intent_classifier.py` -- Stage 1 keyword matching
- `bot/formatters.py` -- Message formatting
- `bot/claude_bridge.py` -- subprocess wrapper for Claude Code CLI
- `bot/context_manager.py` -- Conversation context builder
- `mcp_server.py` -- All MCP tools (core data query tools first)
- `.claude/settings.local.json` -- MCP registration
- `CLAUDE.md` -- Master Claude instructions

**Validation**: Send "삼전 얼마야?" via Telegram, get price response. Register MCP server with `claude mcp add`, verify `claude` can call `get_price("005930")`.

### Phase 3: Signal Detection + Technical Engine (Week 3)
**Goal: Automated anomaly detection and technical analysis.**

Files to create:
- `engine/signal_detector.py`
- `engine/signal_filter.py` (7-filter pipeline)
- `engine/technical.py`
- `engine/regime_detector.py`
- `engine/decay_engine.py`
- `engine/impact_calculator.py`
- `collectors/polymarket.py`
- `collectors/yfinance_fallback.py`

**Validation**: Inject a price spike into test data, verify signal_quality record created with all 7 filter scores.

### Phase 4: Analysis Agents + Reports (Week 4)
**Goal: Full multi-agent analysis producing Tier 3 reports.**

Files to create:
- `.claude/agents/leader.md`
- `.claude/agents/goguma.md`
- `.claude/agents/macro-expert.md` (and all 5 other domain experts)
- `scheduler/report_orchestrator.py`
- `scheduler/event_calendar.py`
- MCP tools for predictions, causal links, strategy notes

Set up schedule triggers for Tier 3 reports.

**Validation**: Manually trigger a full report cycle. Verify leader activates experts, predictions saved to DB, report sent to Telegram.

### Phase 5: Portfolios + Notion (Week 5)
**Goal: 3-portfolio system + Notion dashboards.**

Files to create:
- `notion/client.py`
- `notion/report_publisher.py`
- `notion/dashboard_updater.py`
- MCP tools for portfolio management, virtual trades
- `scripts/migrate_from_potato_fin.py` -- Migrate existing trades

**Validation**: User sends portfolio snapshot via Telegram. Goguma makes virtual trade. Compare portfolios command works. Reports appear in Notion.

### Phase 6: Self-Improvement + Operations (Week 6)
**Goal: Autonomous improvement cycle.**

Files to create:
- `.claude/agents/improvement.md`
- `.claude/agents/qa.md`
- `.claude/agents/devops.md`
- `ops/health_monitor.py`
- `ops/db_maintenance.py`
- `ops/deploy.py`
- `engine/prediction_evaluator.py`
- `invest.service` (systemd)

Set up schedule trigger for daily improvement cycle.

**Validation**: Run improvement agent. It identifies an issue, creates a branch, QA validates, auto-merges. Verify Telegram notification.

### Phase 7: Hardening + Crypto (Week 7)
**Goal: Production-ready with all asset classes.**

Files to create:
- `collectors/upbit.py` -- Crypto OHLCV history
- `tests/` -- Full test suite
- Additional error handling, retry logic, circuit breakers

**Validation**: Full system running 24/7. All 3 tiers of reporting working. Autonomous improvement cycles running. All asset classes covered.

---

### Critical Files for Implementation
- `/home/bravopotato/Spaces/finspace/invest/db.py` -- The entire schema and all CRUD operations. Everything depends on this.
- `/home/bravopotato/Spaces/finspace/invest/mcp_server.py` -- The bridge between Claude Code agents and all financial data. Without this, agents are blind.
- `/home/bravopotato/Spaces/finspace/invest/main.py` -- The asyncio entry point that starts bot, scheduler, and health monitor. MCP server is a separate process spawned by Claude Code.
- `/home/bravopotato/Spaces/finspace/invest/bot/claude_bridge.py` -- The subprocess integration that routes Telegram messages to Claude Code and back. This is the critical path for the natural language interface.
- `/home/bravopotato/Spaces/finspace/invest/.claude/agents/leader.md` -- The leader agent prompt that orchestrates all analysis. Gets the multi-agent system right or wrong.