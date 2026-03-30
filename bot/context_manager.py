"""Telegram conversation context builder for Claude Code."""

import json
from db import Database


def build_context(db: Database, chat_id: str, current_text: str,
                  reply_to_message_id: int | None = None) -> str:
    """Build conversation context string for Claude Code prompt."""
    parts = []

    # 1. If this is a reply, fetch the original message and its context
    if reply_to_message_id:
        original = db.get_message_by_telegram_id(reply_to_message_id)
        if original:
            parts.append(f"[사용자가 다음 메시지에 reply함]\n{original['text']}")

            # If the original was a report or alert, fetch details
            ctx_type = original["context_type"]
            ctx_ref = original["context_ref"]
            if ctx_type == "report" and ctx_ref:
                report = db.query_one(
                    "SELECT content_telegram FROM reports WHERE cycle_id=?",
                    (ctx_ref,))
                if report and report["content_telegram"]:
                    summary = report["content_telegram"][:2000]
                    parts.append(f"[관련 보고서 요약]\n{summary}")
            elif ctx_type == "alert" and ctx_ref:
                signal = db.query_one(
                    "SELECT * FROM signal_quality WHERE id=?",
                    (int(ctx_ref),))
                if signal:
                    parts.append(
                        f"[관련 신호] {signal['ticker']} {signal['signal_type']} "
                        f"품질={signal['final_quality']:.2f}")

    # 2. Recent conversation (last 10 messages)
    recent = db.get_recent_messages(chat_id, limit=10)
    if recent:
        parts.append("[최근 대화]")
        for msg in reversed(recent):  # oldest first
            role = "사용자" if msg["role"] == "user" else "봇"
            text = msg["text"][:200]
            parts.append(f"{role}: {text}")

    # 3. Pending actions
    pending = db.get_pending_action(chat_id)
    if pending:
        params = json.loads(pending["params_json"])
        parts.append(f"[대기 중인 액션: {pending['description']}]")
        parts.append(f"[액션 파라미터: {json.dumps(params, ensure_ascii=False)}]")

    # 4. Current user message
    parts.append(f"\n[현재 사용자 메시지]\n{current_text}")

    return "\n---\n".join(parts)
