"""7-stage false signal filter pipeline."""

import logging
from datetime import datetime
from dataclasses import dataclass

from db import Database
from engine.signal_detector import Signal

logger = logging.getLogger(__name__)


@dataclass
class FilteredSignal:
    signal: Signal
    volume_score: float = 1.0
    breadth_score: float = 1.0
    liquidity_score: float = 1.0
    dedup_score: float = 1.0
    stophunt_score: float = 1.0
    crossasset_score: float = 1.0
    historical_score: float = 1.0
    final_quality: float = 1.0


def filter_1_volume(db: Database, signal: Signal) -> float:
    """Volume confirmation: price move should have above-average volume."""
    if signal.signal_type != "price_move":
        return 1.0  # N/A for non-price signals

    latest = db.get_latest_price(signal.ticker)
    if not latest or not latest["volume"]:
        return 0.5

    avg_row = db.query_one(
        "SELECT AVG(volume) as avg_vol FROM stock_prices "
        "WHERE ticker=? AND interval='realtime' AND volume>0 "
        "ORDER BY timestamp DESC LIMIT 20", (signal.ticker,))

    if not avg_row or not avg_row["avg_vol"] or avg_row["avg_vol"] == 0:
        return 0.5

    ratio = latest["volume"] / avg_row["avg_vol"]
    if ratio >= 2.0:
        return 1.0
    if ratio >= 1.0:
        return 0.8
    if ratio >= 0.5:
        return 0.5
    return 0.3


def filter_2_breadth(db: Database, signal: Signal) -> float:
    """Market breadth: index up but few stocks rising = weak signal."""
    # Simplified: check if KOSPI and individual stock move in same direction
    kospi = db.get_latest_indicator("index", "KOSPI")
    if not kospi or kospi["change_pct"] is None:
        return 0.7

    if signal.signal_type == "price_move":
        # Same direction = confirmed
        if (signal.raw_magnitude > 0 and kospi["change_pct"] > 0) or \
           (signal.raw_magnitude < 0 and kospi["change_pct"] < 0):
            return 1.0
        return 0.5

    return 1.0


def filter_3_liquidity(db: Database, signal: Signal) -> float:
    """Liquidity/session filter: signals during low-liquidity periods get discounted."""
    now = datetime.now()
    hour = now.hour
    minute = now.minute

    # Weekend
    if now.weekday() >= 5:
        return 0.5

    # Korean lunch break (11:30-13:00)
    if hour == 11 and minute >= 30 or hour == 12:
        return 0.7

    # Pre-market (before 09:00)
    if hour < 9:
        return 0.3

    # After-hours (after 15:30)
    if hour >= 16:
        return 0.5

    return 1.0


def filter_4_dedup(db: Database, signal: Signal) -> float:
    """News deduplication: repeated signals for same ticker get discounted."""
    if signal.signal_type not in ("price_move", "volume_spike"):
        return 1.0

    # Check similar signals in last 2 hours
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(hours=2)).isoformat()
    count = db.query_one(
        "SELECT COUNT(*) as cnt FROM signal_quality "
        "WHERE ticker=? AND signal_type=? AND created_at>?",
        (signal.ticker, signal.signal_type, cutoff))

    if count and count["cnt"]:
        n = count["cnt"]
        if n == 0:
            return 1.0
        if n == 1:
            return 0.3
        return 0.1
    return 1.0


def filter_5_stophunt(db: Database, signal: Signal) -> float:
    """Stop-loss hunting detection: brief support break followed by recovery."""
    # Simplified: if price dropped then recovered within 5 minutes
    if signal.signal_type != "price_move" or signal.raw_magnitude >= 0:
        return 1.0  # Only check downward moves

    # Check if price recovered
    latest = db.get_latest_price(signal.ticker)
    if latest and latest["change_pct"] is not None and latest["change_pct"] > 0:
        return 0.1  # Price already recovered = likely stop hunt
    return 1.0


def filter_6_crossasset(db: Database, signal: Signal) -> float:
    """Cross-asset validation: do other markets agree?"""
    if signal.signal_type == "polymarket_shift":
        return 1.0  # Polymarket is itself a cross-asset signal

    agreements = 0
    total_checks = 0

    # Bond yields
    bond = db.get_latest_indicator("bond", "US10YT=RR")
    if bond and bond["change_pct"] is not None:
        total_checks += 1
        # Rising yields = risk-on if stock is up, risk-off if down
        if (signal.raw_magnitude > 0 and bond["change_pct"] > 0) or \
           (signal.raw_magnitude < 0 and bond["change_pct"] < 0):
            agreements += 1

    # VIX
    vix = db.get_latest_indicator("index", ".VIX")
    if vix and vix["change_pct"] is not None:
        total_checks += 1
        # VIX falling = risk-on (stocks up), VIX rising = risk-off
        if (signal.raw_magnitude > 0 and vix["change_pct"] < 0) or \
           (signal.raw_magnitude < 0 and vix["change_pct"] > 0):
            agreements += 1

    # Gold
    gold = db.get_latest_indicator("commodity", "GC")
    if gold and gold["change_pct"] is not None:
        total_checks += 1
        # Gold up = risk-off, gold down = risk-on
        if (signal.raw_magnitude > 0 and gold["change_pct"] < 0) or \
           (signal.raw_magnitude < 0 and gold["change_pct"] > 0):
            agreements += 1

    # USD/KRW
    fx = db.get_latest_indicator("fx", "FX_USDKRW")
    if fx and fx["change_pct"] is not None:
        total_checks += 1
        # Won strengthening (FX down) = risk-on for Korean stocks
        if (signal.raw_magnitude > 0 and fx["change_pct"] < 0) or \
           (signal.raw_magnitude < 0 and fx["change_pct"] > 0):
            agreements += 1

    if total_checks == 0:
        return 0.7  # No data = slight discount
    ratio = agreements / total_checks
    if ratio >= 0.6:
        return 1.0
    if ratio >= 0.4:
        return 0.7
    return 0.5


def filter_7_historical(db: Database, signal: Signal) -> float:
    """Historical validation: how often was this signal type correct?"""
    rows = db.query(
        "SELECT was_real FROM signal_quality "
        "WHERE ticker=? AND signal_type=? AND was_real IS NOT NULL "
        "ORDER BY created_at DESC LIMIT 20",
        (signal.ticker, signal.signal_type))

    if not rows or len(rows) < 5:
        return 0.7  # Not enough data = slight discount

    correct = sum(1 for r in rows if r["was_real"] == 1)
    rate = correct / len(rows)
    if rate >= 0.7:
        return 1.0
    if rate >= 0.5:
        return 0.7
    return 0.3


def run_filter_pipeline(db: Database, signals: list[Signal]) -> list[FilteredSignal]:
    """Run all 7 filters on each signal. Returns filtered signals with quality scores."""
    results = []

    for signal in signals:
        fs = FilteredSignal(signal=signal)
        fs.volume_score = filter_1_volume(db, signal)
        fs.breadth_score = filter_2_breadth(db, signal)
        fs.liquidity_score = filter_3_liquidity(db, signal)
        fs.dedup_score = filter_4_dedup(db, signal)
        fs.stophunt_score = filter_5_stophunt(db, signal)
        fs.crossasset_score = filter_6_crossasset(db, signal)
        fs.historical_score = filter_7_historical(db, signal)

        # Final quality = product of all scores
        fs.final_quality = (
            fs.volume_score * fs.breadth_score * fs.liquidity_score *
            fs.dedup_score * fs.stophunt_score * fs.crossasset_score *
            fs.historical_score
        )

        # Save to DB
        db.insert("signal_quality",
                  timestamp=signal.timestamp,
                  ticker=signal.ticker,
                  signal_type=signal.signal_type,
                  raw_magnitude=signal.raw_magnitude,
                  volume_score=fs.volume_score,
                  breadth_score=fs.breadth_score,
                  liquidity_score=fs.liquidity_score,
                  dedup_score=fs.dedup_score,
                  stophunt_score=fs.stophunt_score,
                  crossasset_score=fs.crossasset_score,
                  historical_score=fs.historical_score,
                  final_quality=fs.final_quality,
                  description=signal.description)

        results.append(fs)
        logger.info("Signal %s %s quality=%.3f",
                     signal.ticker, signal.signal_type, fs.final_quality)

    return results
