"""FastMCP server: exposes financial data tools to Claude Code agents."""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP
from db import Database

mcp = FastMCP("fin-invest")
db = Database()


# ─── Data Query Tools ───

@mcp.tool()
def get_price(ticker: str) -> str:
    """Get latest price for a stock ticker."""
    row = db.get_latest_price(ticker)
    if not row:
        return f"{ticker}: 데이터 없음"
    return json.dumps(dict(row), ensure_ascii=False, default=str)


@mcp.tool()
def get_chart(ticker: str, period: str = "3m", interval: str = "daily") -> str:
    """Get historical OHLCV chart data."""
    days = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "2y": 730}.get(period, 90)
    rows = db.get_price_history(ticker, interval=interval, days=days)
    if not rows:
        return f"{ticker}: 차트 데이터 없음"
    data = [dict(r) for r in rows]
    return json.dumps(data[-50:], ensure_ascii=False, default=str)  # Last 50 entries


@mcp.tool()
def get_fundamentals(ticker: str) -> str:
    """Get stock fundamentals (PER, PBR, EPS, market cap, investor flow)."""
    row = db.query_one(
        "SELECT * FROM stock_prices WHERE ticker=? AND interval='daily' "
        "ORDER BY timestamp DESC LIMIT 1", (ticker,))
    if not row:
        return f"{ticker}: 펀더멘탈 데이터 없음"
    return json.dumps(dict(row), ensure_ascii=False, default=str)


@mcp.tool()
def get_investor_flow(ticker: str) -> str:
    """Get recent investor flow data (foreign/institutional/individual net buy)."""
    rows = db.query(
        "SELECT timestamp, foreign_net_buy, institution_net_buy, individual_net_buy "
        "FROM stock_prices WHERE ticker=? AND interval='daily' "
        "AND foreign_net_buy IS NOT NULL "
        "ORDER BY timestamp DESC LIMIT 5", (ticker,))
    if not rows:
        return f"{ticker}: 수급 데이터 없음"
    return json.dumps([dict(r) for r in rows], ensure_ascii=False, default=str)


@mcp.tool()
def get_crypto(symbol: str = "") -> str:
    """Get latest crypto prices. If symbol is empty, returns all watched crypto."""
    if symbol:
        row = db.query_one(
            "SELECT * FROM crypto_prices WHERE symbol=? "
            "ORDER BY timestamp DESC LIMIT 1", (symbol,))
        return json.dumps(dict(row), ensure_ascii=False, default=str) if row else f"{symbol}: 없음"

    watched = db.get_watched_crypto()
    result = []
    for c in watched:
        row = db.query_one(
            "SELECT * FROM crypto_prices WHERE symbol=? "
            "ORDER BY timestamp DESC LIMIT 1", (c["symbol"],))
        if row:
            result.append(dict(row))
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
def get_polymarket(market_id: str = "") -> str:
    """Get Polymarket event data."""
    if market_id:
        row = db.query_one(
            "SELECT * FROM polymarket_prices WHERE market_id=? "
            "ORDER BY timestamp DESC LIMIT 1", (market_id,))
        return json.dumps(dict(row), ensure_ascii=False, default=str) if row else "없음"

    watched = db.get_watched_polymarkets()
    result = []
    for p in watched:
        row = db.query_one(
            "SELECT * FROM polymarket_prices WHERE market_id=? "
            "ORDER BY timestamp DESC LIMIT 1", (p["market_id"],))
        if row:
            d = dict(row)
            d["question"] = p["question"]
            result.append(d)
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
def get_indices() -> str:
    """Get latest values for all tracked market indices."""
    rows = db.query(
        "SELECT DISTINCT code, name, value, change_pct, timestamp "
        "FROM market_indicators WHERE category='index' "
        "GROUP BY code HAVING timestamp=MAX(timestamp)")
    return json.dumps([dict(r) for r in rows], ensure_ascii=False, default=str)


@mcp.tool()
def get_market_data(category: str = "") -> str:
    """Get FX, commodities, bonds data. Filter by category (fx/commodity/bond) or all."""
    if category:
        rows = db.query(
            "SELECT DISTINCT code, name, value, change_pct, timestamp "
            "FROM market_indicators WHERE category=? "
            "GROUP BY code HAVING timestamp=MAX(timestamp)", (category,))
    else:
        rows = db.query(
            "SELECT DISTINCT category, code, name, value, change_pct, timestamp "
            "FROM market_indicators WHERE category IN ('fx','commodity','bond') "
            "GROUP BY category, code HAVING timestamp=MAX(timestamp)")
    return json.dumps([dict(r) for r in rows], ensure_ascii=False, default=str)


@mcp.tool()
def get_technical(ticker: str) -> str:
    """Get technical indicators computed from stored OHLCV data."""
    rows = db.get_price_history(ticker, interval="daily", days=200)
    if len(rows) < 20:
        return f"{ticker}: 기술 분석에 필요한 데이터 부족 ({len(rows)}일)"

    closes = [r["price"] for r in rows if r["price"]]
    if len(closes) < 20:
        return f"{ticker}: 유효 가격 데이터 부족"

    # Compute indicators
    result = {"ticker": ticker, "data_points": len(closes)}
    result["current_price"] = closes[-1]

    # SMA
    for period in [20, 50, 200]:
        if len(closes) >= period:
            result[f"sma_{period}"] = round(sum(closes[-period:]) / period, 2)

    # RSI (14)
    if len(closes) >= 15:
        gains, losses = [], []
        for i in range(-14, 0):
            diff = closes[i] - closes[i - 1]
            gains.append(max(0, diff))
            losses.append(max(0, -diff))
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        if avg_loss > 0:
            rs = avg_gain / avg_loss
            result["rsi_14"] = round(100 - (100 / (1 + rs)), 2)
        else:
            result["rsi_14"] = 100

    # Bollinger Bands
    if len(closes) >= 20:
        sma20 = sum(closes[-20:]) / 20
        variance = sum((c - sma20) ** 2 for c in closes[-20:]) / 20
        std = variance ** 0.5
        result["bollinger_upper"] = round(sma20 + 2 * std, 2)
        result["bollinger_middle"] = round(sma20, 2)
        result["bollinger_lower"] = round(sma20 - 2 * std, 2)

    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def get_watchlist() -> str:
    """Get all watched stocks, crypto, and polymarket events."""
    stocks = [dict(r) for r in db.get_watched_stocks()]
    crypto = [dict(r) for r in db.get_watched_crypto()]
    poly = [dict(r) for r in db.get_watched_polymarkets()]
    return json.dumps(
        {"stocks": stocks, "crypto": crypto, "polymarkets": poly},
        ensure_ascii=False, default=str)


# ─── Analysis Tools ───

@mcp.tool()
def get_active_impacts(ticker: str) -> str:
    """Get active news impacts + geopolitical risk premiums for a ticker."""
    # Layer 1: Active news events
    events = db.query(
        "SELECT ne.headline, ne.magnitude, ne.half_life_hours, ne.decay_type, "
        "cl.magnitude_pct, cl.chain_depth, cl.chain_confidence "
        "FROM causal_links cl JOIN news_events ne ON cl.event_id=ne.id "
        "WHERE cl.target_ticker=? AND ne.expires_at>datetime('now','localtime') "
        "ORDER BY ne.timestamp DESC", (ticker,))

    # Layer 2: Geopolitical risks
    risks = db.query("SELECT * FROM geopolitical_risks WHERE status!='resolved'")
    relevant_risks = []
    for r in risks:
        affected = json.loads(r["affected_assets"] or "[]")
        if ticker in affected or any(ticker.lower() in a.lower() for a in affected):
            relevant_risks.append(dict(r))

    return json.dumps({
        "layer1_events": [dict(e) for e in events],
        "layer2_risks": relevant_risks,
    }, ensure_ascii=False, default=str)


@mcp.tool()
def get_causal_chain(ticker: str = "", event_type: str = "") -> str:
    """Get active causal chains. Filter by ticker and/or event_type."""
    conditions = ["ne.expires_at>datetime('now','localtime')"]
    params = []
    if ticker:
        conditions.append("cl.target_ticker=?")
        params.append(ticker)
    if event_type:
        conditions.append("ne.event_type=?")
        params.append(event_type)

    where = " AND ".join(conditions)
    rows = db.query(
        f"SELECT ne.headline, ne.event_type, ne.magnitude, ne.timestamp, "
        f"cl.target_ticker, cl.chain_depth, cl.magnitude_pct, "
        f"cl.confidence, cl.chain_confidence, cl.reasoning "
        f"FROM causal_links cl JOIN news_events ne ON cl.event_id=ne.id "
        f"WHERE {where} ORDER BY ne.timestamp DESC", tuple(params))
    return json.dumps([dict(r) for r in rows], ensure_ascii=False, default=str)


@mcp.tool()
def get_geopolitical_risks() -> str:
    """Get all active geopolitical risks (Layer 2)."""
    rows = db.query("SELECT * FROM geopolitical_risks WHERE status!='resolved'")
    return json.dumps([dict(r) for r in rows], ensure_ascii=False, default=str)


@mcp.tool()
def get_signal_quality(ticker: str = "") -> str:
    """Get recent signals with quality scores."""
    if ticker:
        rows = db.query(
            "SELECT * FROM signal_quality WHERE ticker=? "
            "ORDER BY created_at DESC LIMIT 10", (ticker,))
    else:
        rows = db.query(
            "SELECT * FROM signal_quality ORDER BY created_at DESC LIMIT 20")
    return json.dumps([dict(r) for r in rows], ensure_ascii=False, default=str)


@mcp.tool()
def get_events(days_ahead: int = 7) -> str:
    """Get upcoming events from the calendar."""
    cutoff = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")
    rows = db.query(
        "SELECT * FROM events WHERE event_date BETWEEN ? AND ? "
        "ORDER BY event_date, event_time", (today, cutoff))
    return json.dumps([dict(r) for r in rows], ensure_ascii=False, default=str)


@mcp.tool()
def get_regime() -> str:
    """Get current market regime assessment."""
    vix = db.get_latest_indicator("index", ".VIX")
    regime_info = {"vix": dict(vix) if vix else None}

    # Get model params for regime detection
    params = db.query(
        "SELECT param_name, value FROM model_params WHERE category='regime'")
    regime_info["params"] = {p["param_name"]: p["value"] for p in params}

    return json.dumps(regime_info, ensure_ascii=False, default=str)


# ─── Prediction/Strategy Tools ───

@mcp.tool()
def get_predictions(agent: str = "", status: str = "pending") -> str:
    """Get predictions. Filter by agent and/or status."""
    conditions = []
    params = []
    if agent:
        conditions.append("agent_role=?")
        params.append(agent)
    if status:
        conditions.append("status=?")
        params.append(status)

    where = " AND ".join(conditions) if conditions else "1=1"
    rows = db.query(
        f"SELECT * FROM predictions WHERE {where} "
        f"ORDER BY created_at DESC LIMIT 50", tuple(params))
    return json.dumps([dict(r) for r in rows], ensure_ascii=False, default=str)


@mcp.tool()
def get_accuracy(agent: str = "", period: str = "") -> str:
    """Get agent accuracy statistics."""
    conditions = []
    params = []
    if agent:
        conditions.append("agent_role=?")
        params.append(agent)
    if period:
        conditions.append("period=?")
        params.append(period)

    where = " AND ".join(conditions) if conditions else "1=1"
    rows = db.query(
        f"SELECT * FROM agent_accuracy WHERE {where} "
        f"ORDER BY updated_at DESC", tuple(params))
    return json.dumps([dict(r) for r in rows], ensure_ascii=False, default=str)


@mcp.tool()
def get_strategy_notes(agent: str) -> str:
    """Get active strategy notes for an agent."""
    rows = db.query(
        "SELECT * FROM strategy_notes WHERE agent_role=? AND active=1 "
        "AND (expires_at IS NULL OR expires_at>datetime('now','localtime')) "
        "ORDER BY created_at DESC", (agent,))
    return json.dumps([dict(r) for r in rows], ensure_ascii=False, default=str)


@mcp.tool()
def save_prediction(agent_role: str, target_id: str, target_type: str,
                    horizon: str, direction: str, median_pct: float,
                    confidence: int, ci70_low: float, ci70_high: float,
                    ci90_low: float, ci90_high: float,
                    reasoning: str) -> str:
    """Save a prediction."""
    price_row = db.get_latest_price(target_id)
    baseline = price_row["price"] if price_row else 0

    cycle_id = datetime.now().strftime("%Y-%m-%dT%H:%M")
    horizon_map = {"4h": 4, "1d": 24, "5d": 120, "1m": 720}
    hours = horizon_map.get(horizon, 24)
    eval_at = (datetime.now() + timedelta(hours=hours)).isoformat()

    db.insert("predictions",
              cycle_id=cycle_id, agent_role=agent_role,
              target_id=target_id, target_type=target_type,
              predicted_direction=direction,
              predicted_median_pct=median_pct,
              predicted_ci70_low=ci70_low, predicted_ci70_high=ci70_high,
              predicted_ci90_low=ci90_low, predicted_ci90_high=ci90_high,
              confidence=confidence, reasoning=reasoning,
              horizon=horizon, baseline_price=baseline,
              evaluation_at=eval_at)
    return f"예측 저장: {target_id} {direction} {median_pct:+.2f}% (확신도 {confidence})"


@mcp.tool()
def save_causal_link(headline: str, event_type: str, target_ticker: str,
                     chain_depth: int, magnitude_pct: float,
                     confidence: float, reasoning: str) -> str:
    """Save a causal link (event → impact on ticker)."""
    event_id = db.insert("news_events",
                         timestamp=datetime.now().isoformat(),
                         headline=headline, event_type=event_type,
                         magnitude=magnitude_pct)
    db.insert("causal_links",
              event_id=event_id, target_ticker=target_ticker,
              chain_depth=chain_depth, magnitude_pct=magnitude_pct,
              confidence=confidence,
              chain_confidence=confidence ** chain_depth,
              reasoning=reasoning)
    return f"인과 링크 저장: {headline} → {target_ticker} ({chain_depth}차, {magnitude_pct:+.2f}%)"


@mcp.tool()
def update_geopolitical_risk(name: str, status: str, severity: int,
                              risk_premium_json: str,
                              escalation_prob: float,
                              resolution_prob: float) -> str:
    """Create or update a geopolitical risk entry."""
    existing = db.query_one(
        "SELECT id FROM geopolitical_risks WHERE name=?", (name,))
    if existing:
        db.execute(
            "UPDATE geopolitical_risks SET status=?, severity=?, "
            "risk_premium_json=?, escalation_prob=?, resolution_prob=?, "
            "last_updated=datetime('now','localtime') WHERE name=?",
            (status, severity, risk_premium_json,
             escalation_prob, resolution_prob, name))
        return f"지정학 리스크 업데이트: {name} ({status}, severity={severity})"
    else:
        db.insert("geopolitical_risks",
                  name=name, category="general", status=status,
                  severity=severity, risk_premium_json=risk_premium_json,
                  escalation_prob=escalation_prob,
                  resolution_prob=resolution_prob,
                  started_at=datetime.now().isoformat())
        return f"지정학 리스크 생성: {name}"


@mcp.tool()
def save_report(cycle_id: str, report_type: str, content_telegram: str,
                agents_activated: str, duration_seconds: int) -> str:
    """Save a report to DB."""
    db.insert("reports",
              cycle_id=cycle_id, report_type=report_type,
              content_telegram=content_telegram,
              agents_activated=agents_activated,
              duration_seconds=duration_seconds,
              triggered_by="schedule")
    return f"보고서 저장: {cycle_id} ({report_type})"


@mcp.tool()
def update_model_param(category: str, param_name: str, value: float,
                       updated_by: str = "improvement_agent") -> str:
    """Update a model parameter value."""
    db.execute(
        "UPDATE model_params SET value=?, calibration_factor=1.0, "
        "updated_by=?, updated_at=datetime('now','localtime') "
        "WHERE category=? AND param_name=?",
        (value, updated_by, category, param_name))
    return f"파라미터 업데이트: {category}.{param_name} = {value}"


@mcp.tool()
def save_strategy_note(agent_role: str, content: str,
                       valid_regime: str = "all") -> str:
    """Save a strategy note for an agent."""
    expires = (datetime.now() + timedelta(days=30)).isoformat()
    db.insert("strategy_notes",
              agent_role=agent_role, content=content,
              valid_regime=valid_regime, expires_at=expires)
    return f"전략 노트 저장: [{agent_role}] {content[:50]}..."


# ─── Watchlist Management Tools ───

@mcp.tool()
def add_stock(ticker: str, name: str = "", market: str = "KOSPI",
              country: str = "KR") -> str:
    """Add a stock to the watchlist."""
    reuters_code = ""
    if country == "US":
        # Guess Reuters code for NASDAQ
        reuters_code = f"{ticker}.O"
    db.add_stock(ticker, name=name, market=market,
                 country=country, reuters_code=reuters_code)
    return f"종목 추가: {ticker} {name} ({market}, {country})"


@mcp.tool()
def remove_stock(ticker: str) -> str:
    """Remove a stock from the watchlist (soft delete)."""
    db.remove_stock(ticker)
    return f"종목 삭제: {ticker}"


@mcp.tool()
def add_crypto(symbol: str, name: str = "",
               exchange: str = "UPBIT") -> str:
    """Add a cryptocurrency to the watchlist."""
    db.insert("watched_crypto", symbol=symbol, name=name, exchange=exchange)
    return f"암호화폐 추가: {symbol} ({exchange})"


@mcp.tool()
def add_polymarket(market_id: str, question: str = "",
                   category: str = "") -> str:
    """Add a Polymarket event to the watchlist."""
    db.insert("watched_polymarkets",
              market_id=market_id, question=question, category=category)
    return f"폴리마켓 추가: {market_id}"


# ─── Portfolio Tools ───

@mcp.tool()
def get_portfolio(portfolio_type: str = "user") -> str:
    """Get portfolio holdings. Type: user, goguma, or leader."""
    if portfolio_type == "user":
        holdings = db.query("SELECT * FROM user_portfolio")
        cash = db.query("SELECT * FROM user_cash")
    elif portfolio_type == "goguma":
        holdings = db.query("SELECT * FROM goguma_portfolio")
        cash = db.query("SELECT * FROM goguma_cash")
    elif portfolio_type == "leader":
        holdings = db.query(
            "SELECT * FROM leader_recommendations "
            "ORDER BY created_at DESC LIMIT 20")
        cash = []
    else:
        return "Unknown portfolio type"

    return json.dumps({
        "holdings": [dict(r) for r in holdings],
        "cash": [dict(r) for r in cash],
    }, ensure_ascii=False, default=str)


@mcp.tool()
def record_trade(ticker: str, action: str, qty: float, price: float,
                 currency: str = "KRW", name: str = "") -> str:
    """Record a user trade and update portfolio."""
    db.insert("user_trades",
              timestamp=datetime.now().isoformat(),
              ticker=ticker, name=name, action=action,
              qty=qty, price=price, currency=currency)

    # Update portfolio
    existing = db.query_one(
        "SELECT * FROM user_portfolio WHERE ticker=?", (ticker,))

    if action == "buy":
        if existing:
            new_qty = existing["qty"] + qty
            new_avg = ((existing["avg_price"] * existing["qty"]) + (price * qty)) / new_qty
            db.execute(
                "UPDATE user_portfolio SET qty=?, avg_price=?, "
                "updated_at=datetime('now','localtime') WHERE ticker=?",
                (new_qty, new_avg, ticker))
        else:
            db.insert("user_portfolio",
                      ticker=ticker, name=name, qty=qty,
                      avg_price=price, currency=currency)
    elif action == "sell":
        if existing:
            new_qty = existing["qty"] - qty
            if new_qty <= 0:
                db.execute("DELETE FROM user_portfolio WHERE ticker=?", (ticker,))
            else:
                db.execute(
                    "UPDATE user_portfolio SET qty=?, "
                    "updated_at=datetime('now','localtime') WHERE ticker=?",
                    (new_qty, ticker))

    return f"매매 기록: {action} {ticker} {qty}주 @ {price}"


@mcp.tool()
def execute_virtual_trade(ticker: str, action: str, amount: float,
                          reasoning: str = "") -> str:
    """Execute a virtual trade in goguma's portfolio."""
    # Get current price
    price_row = db.get_latest_price(ticker)
    if not price_row or not price_row["price"]:
        return f"{ticker}: 현재가를 조회할 수 없습니다"

    price = price_row["price"]
    qty = amount / price

    db.insert("goguma_trades",
              timestamp=datetime.now().isoformat(),
              ticker=ticker, action=action, qty=qty, price=price,
              reasoning=reasoning)

    # Update goguma portfolio
    existing = db.query_one(
        "SELECT * FROM goguma_portfolio WHERE ticker=?", (ticker,))

    if action == "buy":
        cash = db.query_one("SELECT amount FROM goguma_cash WHERE currency='KRW'")
        if cash and cash["amount"] < amount:
            return f"고구마 현금 부족: ₩{cash['amount']:,.0f} < ₩{amount:,.0f}"

        if existing:
            new_qty = existing["qty"] + qty
            new_avg = ((existing["avg_price"] * existing["qty"]) + (price * qty)) / new_qty
            db.execute(
                "UPDATE goguma_portfolio SET qty=?, avg_price=?, "
                "updated_at=datetime('now','localtime') WHERE ticker=?",
                (new_qty, new_avg, ticker))
        else:
            db.insert("goguma_portfolio",
                      ticker=ticker, qty=qty, avg_price=price, currency="KRW")

        db.execute("UPDATE goguma_cash SET amount=amount-? WHERE currency='KRW'",
                   (amount,))

    elif action == "sell":
        if not existing:
            return f"고구마가 {ticker}를 보유하고 있지 않습니다"
        proceeds = min(qty, existing["qty"]) * price
        new_qty = existing["qty"] - qty
        if new_qty <= 0:
            db.execute("DELETE FROM goguma_portfolio WHERE ticker=?", (ticker,))
        else:
            db.execute(
                "UPDATE goguma_portfolio SET qty=?, "
                "updated_at=datetime('now','localtime') WHERE ticker=?",
                (new_qty, ticker))
        db.execute("UPDATE goguma_cash SET amount=amount+? WHERE currency='KRW'",
                   (proceeds,))

    return f"고구마 {action}: {ticker} {qty:.2f}주 @ ₩{price:,.0f} (₩{amount:,.0f})"


@mcp.tool()
def compare_portfolios() -> str:
    """Compare user vs goguma vs benchmarks."""
    snapshots = db.query(
        "SELECT * FROM portfolio_snapshots "
        "ORDER BY timestamp DESC LIMIT 10")
    return json.dumps([dict(r) for r in snapshots], ensure_ascii=False, default=str)


@mcp.tool()
def update_portfolio_snapshot(portfolio_type: str, holdings_json: str,
                               cash_json: str) -> str:
    """Replace entire portfolio with a snapshot."""
    import json as _json
    holdings = _json.loads(holdings_json)
    cash = _json.loads(cash_json)

    table = "user_portfolio" if portfolio_type == "user" else "goguma_portfolio"
    cash_table = "user_cash" if portfolio_type == "user" else "goguma_cash"

    # Clear existing
    db.execute(f"DELETE FROM {table}")
    db.execute(f"DELETE FROM {cash_table}")

    # Insert new holdings
    for h in holdings:
        db.insert(table, **h)

    # Insert cash
    for c in cash:
        db.insert(cash_table, **c)

    return f"{portfolio_type} 포트폴리오 스냅샷 업데이트: {len(holdings)}종목"


if __name__ == "__main__":
    mcp.run()
