# Decision Log — 의사결정 기록

## 2026-03-30

### DEC-001: Python + Claude Code (API 아님)
- **결정**: Claude API(anthropic SDK) 대신 Claude Code를 직접 사용
- **이유**: Max 구독 비용으로 고정, 서브에이전트/MCP 네이티브 활용
- **영향**: subprocess로 CLI 호출, MCP 서버는 독립 프로세스

### DEC-002: 네이버 API 최우선
- **결정**: yfinance 대신 네이버 API를 1순위로 사용
- **이유**: 한국 주식 펀더멘탈(PER/PBR/수급/컨센서스) 네이버에서만 제공
- **영향**: 폴링 70초, front-api 5분

### DEC-003: 에이전트 최소 Sonnet
- **결정**: Haiku 사용 금지, 리더/고구마는 Opus
- **이유**: 분석 품질이 투자 수익에 직결
- **영향**: Claude Code Max 구독 필요

### DEC-004: 텔레그램 자연어 처리
- **결정**: 슬래시 명령어 대신 자연어
- **이유**: 포트폴리오 스냅샷, 매매 기록 등을 자연스럽게 처리
- **영향**: 모든 메시지가 Claude Code를 거침

### DEC-005: GitHub 중심 협업
- **결정**: Notion 철회, GitHub Issues/PR/Wiki/Projects 활용
- **이유**: 에이전트 간 PR 리뷰, 의사결정 추적, 투명한 협업
- **영향**: 모든 개선은 Issue → PR → Review → Merge

### DEC-006: Docker 배포
- **결정**: Docker Compose 기반 배포
- **이유**: 환경 일관성, 재시작 정책
- **영향**: Dockerfile, docker-compose.yml, invest.service

## 2026-03-31

### DEC-007: 3개 포트폴리오
- **결정**: 사용자 실제 + 고구마 가상(1억) + 리더 추천
- **이유**: 추천 성과 검증, 벤치마크 비교
- **영향**: portfolio_snapshots 테이블, compare_portfolios MCP 도구

### DEC-008: 고구마 독립성
- **결정**: 고구마는 별도 subprocess로 실행 (리더의 서브에이전트 아님)
- **이유**: 앵커링 방지, 팀 분석과 완전 독립
- **영향**: report_orchestrator에서 두 개의 call_claude_async 병렬 실행
