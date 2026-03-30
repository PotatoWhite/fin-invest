# fin-invest — 투자 모니터링 시스템

## 프로젝트 개요
네이버 API 기반 투자 모니터링 + 멀티에이전트 분석 + 자기개선 시스템.
Python 데몬(데이터 수집/신호/텔레그램) + Claude Code(분석/예측/개선).

## 핵심 규칙
- Claude API 사용 금지. Claude Code를 직접 사용한다.
- 모든 에이전트는 최소 Sonnet. 리더/고구마는 Opus.
- 예측은 확률 분포 출력 (점추정 금지). 엣지 없으면 패스.
- 한국어로 분석/보고.
- 고구마는 팀 분석을 절대 보지 않는다 (독립).

## MCP 서버
`mcp_server.py`에 34개 도구. 에이전트는 이 도구를 통해 모든 데이터에 접근.
주요 도구: get_price, get_chart, get_fundamentals, get_technical, get_regime,
get_signal_quality, get_active_impacts, get_causal_chain, get_predictions,
get_accuracy, get_strategy_notes, save_prediction, save_causal_link,
get_portfolio, record_trade, execute_virtual_trade, compare_portfolios

## 데이터 소스
네이버 API 최우선 (폴링 70초). yfinance는 fallback만.
DB: SQLite WAL (`data/invest.db`). 스키마는 `db.py` 참조.

## 보고서 구성 (Tier 3)
1. 레짐 판정
2. 시장 데이터 요약
3. 이전 예측 검증
4. 인과 사슬 현황
5. 신호 현황
6. 새 예측 (확률 분포 + 요인 분해)
7. 에이전트 정확도 리더보드
8. 고구마 코너
9. 이벤트 캘린더
10. 비용/소요시간

## 분석 프레임워크
1. 레짐 판별 → 2. 인과 사슬 → 3. 다중 시간축 → 4. 리스크 관리 → 5. 교차 검증

## 3-Layer 시장 영향 모델
Layer 1: 뉴스 이벤트 (반감기 감쇠)
Layer 2: 지정학 리스크 (상태 추적, 해소까지 유지)
Layer 3: 폴리마켓 확률 (Layer 2 자동 업데이트)

## 충격 크기 = Base × Surprise × Regime × Positioning × Liquidity

## 파일 구조
- `config.py` — 설정
- `db.py` — DB 스키마 + CRUD
- `main.py` — asyncio 진입점
- `mcp_server.py` — MCP 도구 (독립 프로세스)
- `collectors/` — 데이터 수집 (naver_stock, naver_index, naver_market)
- `engine/` — 분석 엔진 (signal, impact, technical, regime)
- `bot/` — 텔레그램 (자연어, Claude 브릿지, 컨텍스트)
- `scheduler/` — APScheduler 잡
- `.claude/agents/` — 12개 서브에이전트

## 참조 문서
- REQUIREMENTS.md: 요구사항 정의서
- DESIGN.md: 상세 설계
- NAVER_API_RESEARCH.md: 네이버 API 엔드포인트
