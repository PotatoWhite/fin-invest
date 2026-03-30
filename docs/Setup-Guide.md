# Setup Guide — 설치/설정 가이드

## 1. 사전 요구사항
- Python 3.12+
- Claude Code CLI (`claude`) 설치
- 텔레그램 봇 (BotFather로 생성)
- Git

## 2. 설치

```bash
git clone git@github.com:PotatoWhite/fin-invest.git
cd fin-invest
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. 환경 설정

```bash
# .env 파일 생성
cat > .env << EOF
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
EOF
```

## 4. DB 초기화

```bash
python scripts/init_db.py
```
43개 model_params 시드 + 고구마 1억 초기 자본.

## 5. 실행

```bash
# 직접 실행
python main.py

# Docker
docker compose up -d
```

## 6. MCP 서버 등록

`.claude/settings.local.json`에 MCP 서버 등록:
```json
{
  "mcpServers": {
    "fin-invest": {
      "command": "/path/to/.venv/bin/python3",
      "args": ["/path/to/mcp_server.py"],
      "cwd": "/path/to/fin-invest"
    }
  }
}
```

## 7. 종목 추가

텔레그램에서 자연어로:
- "삼성전자 추가해줘"
- "NVDA 봐줘"
- "비트코인도 추적해"

## 8. 확인

```bash
# DB 상태 확인
python -c "from db import Database; db=Database(); print(db.table_counts())"

# 테스트 실행
python -m pytest tests/ -v
```
