"""Event calendar manager: D-7/3/1/0 notifications and agent activation."""

import json
import logging
from datetime import datetime, timedelta

from db import Database

logger = logging.getLogger(__name__)


def check_upcoming_events(db: Database) -> list[dict]:
    """Check for events at D-7, D-3, D-1, D-Day thresholds."""
    today = datetime.now().strftime("%Y-%m-%d")
    alerts = []

    for days_ahead, label in [(0, "D-Day"), (1, "D-1"), (3, "D-3"), (7, "D-7")]:
        target_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        events = db.query(
            "SELECT * FROM events WHERE event_date=?", (target_date,))

        for event in events:
            alerts.append({
                "label": label,
                "event": dict(event),
                "agents_to_activate": json.loads(
                    event["activated_agents"] or "[]"),
            })

    if alerts:
        logger.info("Event alerts: %d (%s)",
                     len(alerts),
                     ", ".join(f"{a['label']}: {a['event']['name']}" for a in alerts))

    return alerts


def determine_active_experts(db: Database, regime: str,
                              signals: list, events: list) -> list[str]:
    """Determine which domain experts to activate for this cycle."""
    experts = []

    # Always: leader + goguma are handled separately

    # Event-driven activation
    event_agents = set()
    for alert in events:
        for agent in alert.get("agents_to_activate", []):
            event_agents.add(agent)

    experts.extend(event_agents)

    # Signal-driven: activate based on signal types
    signal_tickers = set()
    for sig in signals:
        ticker = sig.get("ticker", "") if isinstance(sig, dict) else getattr(sig, "ticker", "")
        signal_tickers.add(ticker)

    # If Korean stocks have signals → korea-expert
    kr_stocks = db.get_watched_stocks(country="KR")
    kr_tickers = {s["ticker"] for s in kr_stocks}
    if signal_tickers & kr_tickers:
        experts.append("korea")
        experts.append("micro")

    # US stocks
    us_stocks = db.get_watched_stocks(country="US")
    us_tickers = {s["ticker"] for s in us_stocks}
    if signal_tickers & us_tickers:
        experts.append("usmarket")
        experts.append("micro")

    # Market hours-based
    now = datetime.now()
    h = now.hour
    if now.weekday() < 5:
        if 9 <= h <= 15:
            experts.append("korea")
        if h >= 22 or h < 5:
            experts.append("usmarket")

    # Regime-based: crisis/risk-off → macro + finance always
    if regime in ("crisis", "risk_off"):
        experts.extend(["macro", "finance", "global"])

    # Deduplicate
    return list(set(experts))
