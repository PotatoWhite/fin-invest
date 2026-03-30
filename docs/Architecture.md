# Architecture

## 아키텍처 개요
```
Python Daemon (24/7)          Claude Code (on-demand)
├── Data Collectors           ├── Leader Agent (Opus)
│   ├── Naver Stock (70s)     ├── Goguma Agent (Opus)
│   ├── Naver Index (70s)     ├── 7 Domain Experts (Sonnet)
│   ├── Naver Market (5m)     └── 3 Ops Agents (Sonnet)
│   └── Crypto (5m)           
├── Signal Engine             MCP Server (34 tools)
│   ├── Detector              ├── Data Query (9)
│   ├── 7-Filter Pipeline     ├── Analysis (6)
│   └── 3-Layer Impact        ├── Prediction (6)
├── Telegram Bot              ├── Portfolio (5)
│   ├── NLU (2-stage)         └── Watchlist (5)
│   └── Claude Bridge         
├── Scheduler (APScheduler)   
└── Health Monitor            
```

## 데이터 흐름
1. Collectors → DB (70s/5m)
2. Signal Detector → 7-Filter → Tier 2 Alert
3. Schedule Trigger → Leader → Experts → Report
4. Goguma (독립) → Portfolio 관리
5. Report → DB → Telegram + 알림
