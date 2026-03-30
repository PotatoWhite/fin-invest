"""Async Telegram bot with natural language processing."""

import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, MessageHandler, ContextTypes, filters,
)

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from db import Database
from bot.intent_classifier import classify_stage1
from bot.context_manager import build_context
from bot.claude_bridge import call_claude_async
from bot.formatters import chunk_message

logger = logging.getLogger(__name__)


class InvestBot:
    """Telegram bot with natural language interface."""

    def __init__(self, db: Database):
        self.db = db
        self.app = None

    async def start(self):
        if not TELEGRAM_BOT_TOKEN:
            logger.warning("TELEGRAM_BOT_TOKEN not set, bot disabled")
            return

        self.app = (
            ApplicationBuilder()
            .token(TELEGRAM_BOT_TOKEN)
            .build()
        )

        # Handle all text messages
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

        # Handle photos (screenshots)
        self.app.add_handler(
            MessageHandler(filters.PHOTO, self._handle_photo)
        )

        logger.info("Telegram bot starting...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram bot running")

    async def stop(self):
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

    async def send_message(self, text: str, chat_id: str = ""):
        """Send a message to the configured chat. Handles chunking."""
        target = chat_id or TELEGRAM_CHAT_ID
        if not target or not self.app:
            return

        for chunk in chunk_message(text):
            try:
                sent = await self.app.bot.send_message(
                    chat_id=target, text=chunk, parse_mode="Markdown")
                self.db.save_message(
                    message_id=sent.message_id,
                    chat_id=target, role="bot", text=chunk)
            except Exception as e:
                # Fallback: send without Markdown
                logger.warning("Markdown send failed, retrying plain: %s", e)
                try:
                    sent = await self.app.bot.send_message(
                        chat_id=target, text=chunk)
                    self.db.save_message(
                        message_id=sent.message_id,
                        chat_id=target, role="bot", text=chunk)
                except Exception as e2:
                    logger.error("Failed to send message: %s", e2)

    def _is_authorized(self, chat_id: str) -> bool:
        return str(chat_id) == str(TELEGRAM_CHAT_ID)

    async def _handle_message(self, update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return

        chat_id = str(update.effective_chat.id)
        if not self._is_authorized(chat_id):
            return

        text = update.message.text
        reply_to = update.message.reply_to_message
        reply_to_id = reply_to.message_id if reply_to else None

        # Save incoming message
        self.db.save_message(
            message_id=update.message.message_id,
            chat_id=chat_id, role="user", text=text,
            reply_to=reply_to_id)

        # Stage 1: Fast keyword matching
        intent, response = classify_stage1(
            self.db, text, chat_id, reply_to_id)

        if response:
            await self._reply(update, response)
            return

        # Stage 2: Claude Code for complex intents
        # Send "analyzing" indicator
        thinking_msg = await update.message.reply_text("🔍 분석 중...")

        try:
            # Build context
            ctx = build_context(self.db, chat_id, text, reply_to_id)

            # Build prompt
            prompt = (
                "당신은 투자 모니터링 시스템의 텔레그램 인터페이스입니다.\n"
                "사용자의 메시지를 이해하고 적절히 응답하세요.\n"
                "MCP 도구를 사용하여 데이터를 조회할 수 있습니다.\n"
                "한국어로 자연스럽게 응답하세요.\n"
                "액션(종목 추가/삭제, 매매 등)이 필요하면 먼저 제안하고 "
                "사용자 확인을 요청하세요.\n\n"
                f"{ctx}"
            )

            # Choose agent based on intent
            agent = ""
            if "고구마" in text:
                agent = "goguma"

            response = await call_claude_async(prompt, agent=agent)

        except Exception as e:
            logger.error("Claude bridge error: %s", e)
            response = f"분석 중 오류가 발생했습니다: {e}"
        finally:
            # Delete thinking message
            try:
                await thinking_msg.delete()
            except Exception:
                pass

        await self._reply(update, response)

    async def _handle_photo(self, update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
        """Handle photo messages (e.g., brokerage screenshots)."""
        if not update.message:
            return

        chat_id = str(update.effective_chat.id)
        if not self._is_authorized(chat_id):
            return

        caption = update.message.caption or "증권사 스크린샷"

        self.db.save_message(
            message_id=update.message.message_id,
            chat_id=chat_id, role="user",
            text=f"[사진] {caption}")

        # For now, inform the user that image processing will be added later
        await update.message.reply_text(
            "스크린샷 인식 기능은 아직 준비 중입니다.\n"
            "텍스트로 포트폴리오를 알려주세요.\n"
            "예: \"삼전 100주 평단 54200, NVDA 50주 평단 $175\"")

    async def _reply(self, update: Update, text: str):
        chat_id = str(update.effective_chat.id)
        for chunk in chunk_message(text):
            try:
                sent = await update.message.reply_text(
                    chunk, parse_mode="Markdown")
            except Exception:
                sent = await update.message.reply_text(chunk)

            self.db.save_message(
                message_id=sent.message_id,
                chat_id=chat_id, role="bot", text=chunk)
