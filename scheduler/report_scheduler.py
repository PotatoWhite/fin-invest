"""Report scheduling: periodic analysis + 30-min task checker."""

import json
import logging
from datetime import datetime, timedelta

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, KST
from db import Database

logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


def _send_telegram(text: str):
    """Send message via Telegram API directly (no bot instance needed)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured")
        return
    try:
        for i in range(0, len(text), 4096):
            chunk = text[i:i+4096]
            requests.post(TELEGRAM_API,
                          json={"chat_id": TELEGRAM_CHAT_ID, "text": chunk},
                          timeout=10)
    except Exception as e:
        logger.error("Telegram send failed: %s", e)


def morning_briefing(db: Database):
    """아침 뉴스 브리핑 (08:30 KST, 장 개장 전)."""
    logger.info("Running morning briefing...")

    # 전날 미국 시장 요약
    sp = db.get_latest_indicator("index", ".INX")
    nasdaq = db.get_latest_indicator("index", ".IXIC")
    vix = db.get_latest_indicator("index", ".VIX")
    usdkrw = db.get_latest_indicator("fx", "FX_USDKRW")
    us10y = db.get_latest_indicator("bond", "US10YT=RR")
    gold = db.get_latest_indicator("commodity", "GC")
    btc = db.query_one(
        "SELECT * FROM crypto_prices WHERE symbol='BTC' ORDER BY timestamp DESC LIMIT 1")

    # 포트폴리오 현황
    holdings = db.query("SELECT * FROM user_portfolio")

    # 오늘 이벤트
    today = datetime.now().strftime("%Y-%m-%d")
    events = db.query("SELECT * FROM events WHERE event_date=?", (today,))

    # 활성 신호
    signals = db.query(
        "SELECT * FROM signal_quality WHERE final_quality>=0.4 "
        "AND created_at>datetime('now','localtime','-12 hours') "
        "ORDER BY final_quality DESC LIMIT 5")

    # 지정학 리스크
    risks = db.query("SELECT * FROM geopolitical_risks WHERE status!='resolved'")

    lines = ["☀️ 아침 브리핑\n"]

    # 시장
    lines.append("━━ 전날 미국 시장 ━━")
    if sp: lines.append(f"S&P500: {sp['value']:,.1f} ({sp['change_pct']:+.2f}%)")
    if nasdaq: lines.append(f"NASDAQ: {nasdaq['value']:,.1f} ({nasdaq['change_pct']:+.2f}%)")
    if vix: lines.append(f"VIX: {vix['value']:.1f} ({vix['change_pct']:+.2f}%)")
    if usdkrw: lines.append(f"USD/KRW: {usdkrw['value']:,.1f}")
    if us10y: lines.append(f"US 10Y: {us10y['value']:.2f}%")
    if gold: lines.append(f"Gold: ${gold['value']:,.1f}")
    if btc: lines.append(f"BTC: ₩{btc['price_krw']:,.0f}")

    # 이벤트
    if events:
        lines.append("\n━━ 오늘 이벤트 ━━")
        for e in events:
            lines.append(f"⚡ {e['name']} ({e['importance']})")
    else:
        lines.append("\n오늘 주요 이벤트 없음")

    # 신호
    if signals:
        lines.append("\n━━ 활성 신호 ━━")
        for s in signals:
            lines.append(f"📡 {s['description']} (품질: {s['final_quality']:.2f})")

    # 리스크
    if risks:
        lines.append("\n━━ 활성 리스크 ━━")
        for r in risks:
            lines.append(f"⚠️ {r['name']} ({r['status']}, 심각도: {r['severity']})")

    lines.append("\n━━ 오늘의 관전 포인트 ━━")
    if vix and vix['value'] > 25:
        lines.append("• VIX 25+ 유지 중 → 방어적 자세")
    lines.append("• 포트폴리오 18종목 감시 중")
    lines.append(f"• 보유 종목: {len(holdings)}개")

    _send_telegram("\n".join(lines))
    logger.info("Morning briefing sent")


def kr_market_close_report(db: Database):
    """한국 장 마감 보고서 (15:40 KST)."""
    logger.info("Running KR market close report...")

    # 한국 종목 수집
    kr_stocks = db.get_watched_stocks(country="KR")
    lines = ["🇰🇷 한국 장 마감 요약\n"]

    kospi = db.get_latest_indicator("index", "KOSPI")
    if kospi:
        lines.append(f"KOSPI: {kospi['value']:,.2f} ({kospi['change_pct']:+.2f}%)")

    lines.append("\n━━ 보유 한국 종목 ━━")
    for stock in kr_stocks:
        price = db.get_latest_price(stock["ticker"])
        if price and price["price"]:
            change = f"({price['change_pct']:+.2f}%)" if price['change_pct'] else ""
            lines.append(f"{stock['name']}: ₩{price['price']:,.0f} {change}")

    # 수급
    lines.append("\n━━ 수급 ━━")
    for stock in kr_stocks:
        price = db.get_latest_price(stock["ticker"])
        if price and price.get("foreign_net_buy"):
            foreign = price["foreign_net_buy"]
            sign = "순매수" if foreign > 0 else "순매도"
            lines.append(f"{stock['name']}: 외국인 {sign} {abs(foreign):,}")

    _send_telegram("\n".join(lines))
    logger.info("KR market close report sent")


def us_market_close_report(db: Database):
    """미국 장 마감 보고서 (05:05 KST)."""
    logger.info("Running US market close report...")

    lines = ["🇺🇸 미국 장 마감 요약\n"]

    for code, name in [(".INX", "S&P500"), (".IXIC", "NASDAQ"),
                        (".DJI", "Dow"), (".VIX", "VIX")]:
        ind = db.get_latest_indicator("index", code)
        if ind:
            lines.append(f"{name}: {ind['value']:,.2f} ({ind['change_pct']:+.2f}%)")

    lines.append("\n━━ 보유 미국 종목 ━━")
    us_stocks = db.get_watched_stocks(country="US")
    for stock in us_stocks:
        holding = db.query_one(
            "SELECT * FROM user_portfolio WHERE ticker=?", (stock["ticker"],))
        if holding:
            lines.append(f"{holding['name']}: {holding['qty']:.0f}주")

    _send_telegram("\n".join(lines))
    logger.info("US market close report sent")


def periodic_check_30min(db: Database):
    """30분마다 실행: 할 일이 있는지 확인하고 수행."""
    now = datetime.now()
    logger.debug("30-min check at %s", now.strftime("%H:%M"))

    tasks_done = []

    # 1. 미전송 보고서 확인
    unsent = db.query(
        "SELECT * FROM reports WHERE notification_sent=0 "
        "AND content_telegram IS NOT NULL")
    for report in unsent:
        _send_telegram(report["content_telegram"])
        db.execute("UPDATE reports SET notification_sent=1 WHERE id=?",
                   (report["id"],))
        tasks_done.append(f"보고서 전송: {report['cycle_id']}")

    # 2. 만료된 대기 액션 정리
    expired = db.execute(
        "UPDATE pending_actions SET status='expired' "
        "WHERE status='pending' AND expires_at<datetime('now','localtime')")
    if expired > 0:
        tasks_done.append(f"만료 액션 정리: {expired}건")

    # 3. D-Day 이벤트 알림
    today = now.strftime("%Y-%m-%d")
    current_hour = now.strftime("%H:%M")
    events = db.query(
        "SELECT * FROM events WHERE event_date=? AND event_time=?",
        (today, current_hour))
    for e in events:
        _send_telegram(f"⚡ 이벤트 발생: {e['name']}\n중요도: {e['importance']}")
        tasks_done.append(f"이벤트 알림: {e['name']}")

    # 4. 고품질 신호 확인 (최근 30분)
    cutoff = (now - timedelta(minutes=30)).isoformat()
    high_signals = db.query(
        "SELECT * FROM signal_quality "
        "WHERE final_quality>=0.7 AND created_at>?", (cutoff,))
    for sig in high_signals:
        _send_telegram(
            f"🔔 신호 감지: {sig['description']}\n"
            f"품질: {sig['final_quality']:.2f}")
        tasks_done.append(f"신호 알림: {sig['ticker']}")

    # 5. DB 사이즈 경고 (500MB 초과 시)
    size = db.db_size_mb()
    if size > 500:
        _send_telegram(f"⚠️ DB 사이즈 경고: {size:.0f}MB")
        tasks_done.append(f"DB 경고: {size:.0f}MB")

    # 6. 전략 노트 만료 처리
    expired_notes = db.execute(
        "UPDATE strategy_notes SET active=0 "
        "WHERE active=1 AND expires_at<datetime('now','localtime')")
    if expired_notes > 0:
        tasks_done.append(f"만료 전략노트: {expired_notes}건")

    if tasks_done:
        logger.info("30-min check: %s", ", ".join(tasks_done))
