"""Stage 1 intent classification: fast keyword matching in Python."""

import re
from db import Database


# Confirmation patterns
CONFIRM_PATTERNS = re.compile(
    r"^(ㅇㅇ|응|네|해줘|그래|좋아|ㅇㅋ|ok|yes|진행|실행)$", re.IGNORECASE)
REJECT_PATTERNS = re.compile(
    r"^(ㄴㄴ|아니|취소|안해|말어|no|cancel|ㄴ)$", re.IGNORECASE)

# Simple query patterns
PRICE_QUERY = re.compile(r"^(.+?)\s*(얼마|가격|현재가|시세).*$")
LIST_PATTERNS = re.compile(r"^(목록|리스트|뭐\s*보고|감시|watchlist).*$", re.IGNORECASE)
STATUS_PATTERNS = re.compile(r"^(시스템\s*상태|status|헬스).*$", re.IGNORECASE)
PORTFOLIO_PATTERNS = re.compile(r"^(고구마\s*포폴|고구마\s*포트폴리오|내\s*포폴|내\s*포트폴리오).*$")


def classify_stage1(db: Database, text: str, chat_id: str,
                    reply_to_message_id: int | None = None
                    ) -> tuple[str, str | None]:
    """
    Stage 1: Fast keyword-based intent classification.
    Returns (intent, response). If response is None, fall through to Stage 2 (Claude).
    """
    text = text.strip()

    # 1. Confirmation/rejection of pending action
    if CONFIRM_PATTERNS.match(text):
        pending = db.get_pending_action(chat_id)
        if pending:
            return "confirm_action", None  # Let Stage 2 handle execution
        return "unknown", None  # No pending action

    if REJECT_PATTERNS.match(text):
        pending = db.get_pending_action(chat_id)
        if pending:
            db.resolve_pending_action(pending["id"], "rejected")
            return "reject_action", "취소했습니다."
        return "unknown", None

    # 2. System status
    if STATUS_PATTERNS.match(text):
        counts = db.table_counts()
        size = db.db_size_mb()
        health_rows = db.query(
            "SELECT component, status FROM system_health "
            "ORDER BY timestamp DESC LIMIT 10")
        health = "\n".join(
            f"  {h['component']}: {h['status']}" for h in health_rows
        ) if health_rows else "  데이터 없음"
        response = (
            f"시스템 상태\n"
            f"DB: {size:.1f}MB\n"
            f"레코드: {counts}\n"
            f"컴포넌트:\n{health}"
        )
        return "status", response

    # 3. Watchlist query
    if LIST_PATTERNS.match(text):
        stocks = db.get_watched_stocks()
        crypto = db.get_watched_crypto()
        poly = db.get_watched_polymarkets()
        lines = ["감시 목록"]
        if stocks:
            lines.append("\n주식:")
            for s in stocks:
                lines.append(f"  {s['ticker']} {s['name'] or ''} ({s['country']})")
        if crypto:
            lines.append("\n암호화폐:")
            for c in crypto:
                lines.append(f"  {c['symbol']} {c['name'] or ''}")
        if poly:
            lines.append("\n폴리마켓:")
            for p in poly:
                q = (p['question'] or '')[:50]
                lines.append(f"  {p['market_id'][:8]}... {q}")
        if not stocks and not crypto and not poly:
            lines.append("\n감시 종목이 없습니다. 종목을 추가해주세요.")
        return "list", "\n".join(lines)

    # 4. Everything else → Stage 2 (Claude Code)
    return "complex", None
