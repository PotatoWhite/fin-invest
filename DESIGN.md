# 투자 모니터링 시스템 설계

## Context
네이버 주식 API와 폴리마켓 데이터를 5분마다 수집하고, 4시간마다 텔레그램으로 투자 보고서를 전송하는 개인용 모니터링 시스템. 종목은 텔레그램 봇 명령으로 추가/삭제.

## 기술 스택
| 구성요소 | 패키지 | 비고 |
|---------|--------|------|
| Runtime | Python 3.12+ | async 기반 |
| Telegram Bot | python-telegram-bot 22.x | 비동기, 인라인 키보드 |
| HTTP Client | aiohttp 3.x | 네이버/폴리마켓 API 호출 |
| 한국 주식 | pykrx | 네이버 API 실패 시 fallback |
| 스케줄러 | APScheduler 3.11.x | AsyncIOScheduler |
| DB | SQLite (stdlib) | WAL 모드 |

## 프로젝트 구조
```
invest/
├── .env                    # BOT_TOKEN, CHAT_ID
├── .gitignore
├── requirements.txt
├── config.py               # 설정, 환경변수 로딩
├── main.py                 # 진입점: 봇 + 스케줄러 실행
├── db.py                   # SQLite 스키마, CRUD
├── collectors/
│   ├── __init__.py
│   ├── naver_stock.py      # 네이버 주식 API + pykrx fallback
│   └── polymarket.py       # 폴리마켓 API 클라이언트
├── reports/
│   ├── __init__.py
│   └── generator.py        # 4시간 보고서 생성
├── bot/
│   ├── __init__.py
│   ├── telegram_bot.py     # 텔레그램 봇 명령 핸들러
│   └── formatters.py       # 메시지 포맷팅 헬퍼
└── scheduler/
    ├── __init__.py
    └── jobs.py             # APScheduler 작업 정의
```

## DB 스키마 (SQLite)
```sql
-- 감시 종목
CREATE TABLE watched_stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL UNIQUE,        -- '005930'
    name TEXT,                          -- '삼성전자'
    market TEXT DEFAULT 'KOSPI',
    added_at TEXT DEFAULT (datetime('now','localtime')),
    active INTEGER DEFAULT 1
);

-- 감시 폴리마켓
CREATE TABLE watched_polymarkets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL UNIQUE,
    question TEXT,
    slug TEXT,
    category TEXT,
    end_date TEXT,
    added_at TEXT DEFAULT (datetime('now','localtime')),
    active INTEGER DEFAULT 1
);

-- 주식 가격 이력 (5분 간격)
CREATE TABLE stock_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    ticker TEXT NOT NULL,
    price REAL,
    open_price REAL,
    high REAL,
    low REAL,
    volume INTEGER,
    change_pct REAL,
    UNIQUE(timestamp, ticker)
);

-- 폴리마켓 가격 이력 (5분 간격)
CREATE TABLE polymarket_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    market_id TEXT NOT NULL,
    yes_price REAL,
    no_price REAL,
    volume_24h REAL,
    liquidity REAL,
    UNIQUE(timestamp, market_id)
);

-- 보고서 로그
CREATE TABLE reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    report_type TEXT DEFAULT 'periodic',
    content TEXT NOT NULL,
    sent_via TEXT DEFAULT 'telegram'
);
```

## 데이터 흐름
```
텔레그램 사용자
    │ /add_stock, /add_poly, /list, /report ...
    ▼
텔레그램 봇 ◄──── 4시간마다 보고서 전송
    │
    ▼
SQLite DB (invest.db)
    ▲              ▲
    │              │
네이버 수집기    폴리마켓 수집기
(5분 간격)      (5분 간격, 24/7)
(평일 09:00-15:30)
    ▲              ▲
    │              │
APScheduler (AsyncIOScheduler)
```

## 텔레그램 봇 명령어
| 명령어 | 기능 |
|--------|------|
| `/add_stock <종목코드>` | 종목 추가 (네이버 API로 유효성 검증) |
| `/remove_stock <종목코드>` | 종목 삭제 |
| `/add_poly <market_id 또는 검색어>` | 폴리마켓 이벤트 추가 |
| `/remove_poly <id>` | 폴리마켓 이벤트 삭제 |
| `/list` | 감시 중인 종목/이벤트 현황 |
| `/report` | 즉시 보고서 생성 |
| `/status` | 시스템 상태 (마지막 수집 시각, DB 크기) |

## 보고서 샘플 (4시간마다)
```
📊 투자 보고서 (2026-03-30 16:00 KST)
기간: 12:00 ~ 16:00

━━ 한국 주식 ━━
005930 삼성전자  52,300원 (+2.3%)  H:52,800 L:51,200
000660 SK하이닉스 198,500원 (-0.5%)  H:200,100 L:197,200

━━ 폴리마켓 ━━
Will X happen?  67.2% (+3.1pp)  Vol:$1.2M
Will Y happen?  23.8% (-1.2pp)  Vol:$340K

━━ 주요 알림 ━━
⚠ 005930 4시간 내 +2.3% 변동
⚠ "Will X" 확률 +3.1pp 변동

다음 보고서: 20:00 KST
```

### 보고서 지표
- **주식**: 현재가, 기간변동률, 고/저, 변동성(5분 수익률 표준편차), 추세(이동평균 비교)
- **폴리마켓**: 현재 확률, 확률 변동, 24h 거래량, 유동성, 모멘텀(회귀 기울기)
- **알림 기준**: 주식 3%+ 변동, 폴리마켓 5pp+ 변동

## 스케줄러 설정
| 작업 | 주기 | 조건 |
|------|------|------|
| 주식 수집 | 5분 | 평일 08:55~15:35 KST |
| 폴리마켓 수집 | 5분 | 24/7 |
| 보고서 생성 | 4시간 | 항상 |
| DB 정리 | 매일 04:00 | 90일 이전 데이터 삭제 |

## 에러 처리 전략
| 계층 | 전략 |
|------|------|
| 네이버 API 실패 | pykrx fallback → 로그 후 스킵 |
| 텔레그램 전송 실패 | Markdown→plain text fallback, 4096자 분할 |
| DB 에러 | INSERT OR IGNORE (멱등성), WAL 모드 |
| 스케줄러 | misfire_grace_time, max_instances=1, coalesce=True |

## 구현 순서
1. **Phase 1** — 기반: `config.py`, `db.py`, `main.py`
2. **Phase 2** — 수집기: `collectors/naver_stock.py`, `collectors/polymarket.py`
3. **Phase 3** — 텔레그램 봇: `bot/telegram_bot.py`, `bot/formatters.py`
4. **Phase 4** — 스케줄링 + 보고서: `scheduler/jobs.py`, `reports/generator.py`
5. **Phase 5** — 통합 테스트, `.env` 설정 안내

## 검증 방법
1. `python main.py`로 실행 후 텔레그램에서 `/add_stock 005930` 테스트
2. `/list`로 종목 확인
3. 5분 대기 후 DB에 `stock_prices` 데이터 확인
4. `/report`로 수동 보고서 생성 확인
5. 4시간 자동 보고서 수신 확인
