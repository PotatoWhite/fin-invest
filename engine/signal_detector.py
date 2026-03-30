"""Anomaly detection: price moves, volume spikes, technical breakouts."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from db import Database
from config import SIGNAL_PRICE_MOVE_THRESHOLD, SIGNAL_VOLUME_SPIKE_MULTIPLIER

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    ticker: str
    signal_type: str      # 'price_move', 'volume_spike', 'technical_breakout', 'polymarket_shift'
    raw_magnitude: float
    description: str
    timestamp: str


def detect_signals(db: Database) -> list[Signal]:
    """Detect anomalies from recently collected data."""
    signals = []
    now = datetime.now()
    lookback = (now - timedelta(minutes=5)).isoformat()

    # 1. Price move detection (stock prices)
    recent_prices = db.query(
        "SELECT ticker, price, change_pct, volume "
        "FROM stock_prices WHERE timestamp>? AND interval='realtime' "
        "ORDER BY timestamp DESC", (lookback,))

    seen_tickers = set()
    for row in recent_prices:
        ticker = row["ticker"]
        if ticker in seen_tickers:
            continue
        seen_tickers.add(ticker)

        change = row["change_pct"]
        if change is not None and abs(change) >= SIGNAL_PRICE_MOVE_THRESHOLD:
            signals.append(Signal(
                ticker=ticker,
                signal_type="price_move",
                raw_magnitude=change,
                description=f"{ticker} {'급등' if change > 0 else '급락'} {change:+.2f}%",
                timestamp=now.isoformat(),
            ))

    # 2. Volume spike detection
    for row in recent_prices:
        ticker = row["ticker"]
        volume = row["volume"]
        if volume is None:
            continue

        # Get 20-period average volume
        avg_row = db.query_one(
            "SELECT AVG(volume) as avg_vol FROM stock_prices "
            "WHERE ticker=? AND interval='realtime' AND volume>0 "
            "ORDER BY timestamp DESC LIMIT 20", (ticker,))

        if avg_row and avg_row["avg_vol"] and avg_row["avg_vol"] > 0:
            ratio = volume / avg_row["avg_vol"]
            if ratio >= SIGNAL_VOLUME_SPIKE_MULTIPLIER:
                signals.append(Signal(
                    ticker=ticker,
                    signal_type="volume_spike",
                    raw_magnitude=ratio,
                    description=f"{ticker} 거래량 급증 ({ratio:.1f}x 평균)",
                    timestamp=now.isoformat(),
                ))

    # 3. Polymarket probability shift (>5pp in recent data)
    recent_poly = db.query(
        "SELECT market_id, yes_price FROM polymarket_prices "
        "WHERE timestamp>? ORDER BY timestamp DESC", (lookback,))

    # Compare latest vs 1 hour ago
    hour_ago = (now - timedelta(hours=1)).isoformat()
    for row in recent_poly:
        mid = row["market_id"]
        current = row["yes_price"]
        if current is None:
            continue

        prev_row = db.query_one(
            "SELECT yes_price FROM polymarket_prices "
            "WHERE market_id=? AND timestamp<? ORDER BY timestamp DESC LIMIT 1",
            (mid, hour_ago))

        if prev_row and prev_row["yes_price"] is not None:
            shift = (current - prev_row["yes_price"]) * 100  # percentage points
            if abs(shift) >= 5.0:
                signals.append(Signal(
                    ticker=mid,
                    signal_type="polymarket_shift",
                    raw_magnitude=shift,
                    description=f"폴리마켓 {mid[:8]}... 확률 {shift:+.1f}pp 변동",
                    timestamp=now.isoformat(),
                ))

    if signals:
        logger.info("Detected %d signals", len(signals))

    return signals
