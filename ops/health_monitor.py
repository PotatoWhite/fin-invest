"""System health monitoring and report delivery."""

import json
import logging
from datetime import datetime, timedelta

from db import Database

logger = logging.getLogger(__name__)


async def deliver_unsent_reports(db: Database, send_func) -> int:
    """Find reports not yet sent to Telegram and deliver them."""
    unsent = db.query(
        "SELECT * FROM reports WHERE notification_sent=0 "
        "AND content_telegram IS NOT NULL "
        "ORDER BY created_at ASC")

    delivered = 0
    for report in unsent:
        try:
            text = report["content_telegram"]
            if text:
                await send_func(text)
                db.execute(
                    "UPDATE reports SET notification_sent=1 WHERE id=?",
                    (report["id"],))
                delivered += 1
                logger.info("Delivered report: %s", report["cycle_id"])
        except Exception as e:
            logger.error("Failed to deliver report %s: %s",
                         report["cycle_id"], e)

    return delivered


def take_portfolio_snapshot(db: Database):
    """Take snapshots of user and goguma portfolios for tracking."""
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")

    for portfolio_type, table, cash_table in [
        ("user", "user_portfolio", "user_cash"),
        ("goguma", "goguma_portfolio", "goguma_cash"),
    ]:
        holdings = db.query(f"SELECT * FROM {table}")
        cash_rows = db.query(f"SELECT * FROM {cash_table}")

        total_cost = 0.0
        total_value = 0.0
        holdings_data = []

        for h in holdings:
            ticker = h["ticker"]
            qty = h["qty"]
            avg_price = h["avg_price"]
            cost = qty * avg_price

            # Get current price
            price_row = db.get_latest_price(ticker)
            current_price = price_row["price"] if price_row and price_row["price"] else avg_price

            value = qty * current_price
            pnl = value - cost
            pnl_pct = (pnl / cost * 100) if cost > 0 else 0

            total_cost += cost
            total_value += value

            holdings_data.append({
                "ticker": ticker,
                "name": h["name"],
                "qty": qty,
                "avg_price": avg_price,
                "current_price": current_price,
                "value": round(value),
                "pnl": round(pnl),
                "pnl_pct": round(pnl_pct, 2),
            })

        cash_krw = sum(c["amount"] for c in cash_rows
                       if c["currency"] == "KRW") if cash_rows else 0

        total_with_cash = total_value + cash_krw
        total_pnl = total_with_cash - (total_cost + cash_krw)
        total_pnl_pct = (total_pnl / (total_cost + cash_krw) * 100
                         ) if (total_cost + cash_krw) > 0 else 0

        # Get FX rates for reference
        fx = db.get_latest_indicator("fx", "FX_USDKRW")
        fx_rates = {"USD/KRW": fx["value"] if fx else None}

        db.insert("portfolio_snapshots",
                  timestamp=now,
                  portfolio_type=portfolio_type,
                  total_value_krw=round(total_with_cash),
                  total_cost_krw=round(total_cost),
                  total_pnl_krw=round(total_pnl),
                  total_pnl_pct=round(total_pnl_pct, 2),
                  cash_krw=round(cash_krw),
                  holdings_json=json.dumps(holdings_data, ensure_ascii=False),
                  fx_rates_json=json.dumps(fx_rates))

        logger.info("Snapshot %s: ₩%s (PnL: %+.1f%%)",
                     portfolio_type, f"{total_with_cash:,.0f}", total_pnl_pct)


def generate_health_summary(db: Database) -> str:
    """Generate system health summary for Telegram."""
    size = db.db_size_mb()
    counts = db.table_counts()

    health_rows = db.query(
        "SELECT DISTINCT component, status, last_success "
        "FROM system_health "
        "GROUP BY component HAVING timestamp=MAX(timestamp)")

    components = "\n".join(
        f"  {h['component']}: {h['status']}"
        for h in health_rows
    ) if health_rows else "  데이터 없음"

    # Recent predictions accuracy
    accuracy = db.query(
        "SELECT agent_role, direction_rate, ensemble_weight "
        "FROM agent_accuracy WHERE period=(SELECT MAX(period) FROM agent_accuracy) "
        "ORDER BY direction_rate DESC LIMIT 5")
    accuracy_text = "\n".join(
        f"  {a['agent_role']}: {a['direction_rate']*100:.1f}%"
        for a in accuracy
    ) if accuracy else "  아직 데이터 없음"

    return (
        f"📦 시스템 상태\n"
        f"DB: {size:.1f}MB\n"
        f"레코드: {json.dumps(counts, ensure_ascii=False)}\n\n"
        f"컴포넌트:\n{components}\n\n"
        f"정확도 (최근):\n{accuracy_text}"
    )
