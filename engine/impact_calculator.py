"""3-Layer market impact model."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

from db import Database
from engine.decay_engine import calculate_residual, hours_since

logger = logging.getLogger(__name__)


@dataclass
class ImpactResult:
    ticker: str
    layer1_total: float = 0.0       # News event residuals
    layer1_events: list = field(default_factory=list)
    layer2_total: float = 0.0       # Geopolitical risk premiums
    layer2_risks: list = field(default_factory=list)
    layer3_total: float = 0.0       # Polymarket adjustments
    net_impact: float = 0.0


def calculate_layer1(db: Database, ticker: str) -> tuple[float, list]:
    """Layer 1: Sum of active news event residuals."""
    events = db.query(
        "SELECT ne.headline, ne.magnitude, ne.half_life_hours, ne.decay_type, "
        "ne.timestamp, cl.magnitude_pct, cl.chain_confidence "
        "FROM causal_links cl JOIN news_events ne ON cl.event_id=ne.id "
        "WHERE cl.target_ticker=? AND ne.expires_at>datetime('now','localtime')",
        (ticker,))

    total = 0.0
    details = []
    for e in events:
        elapsed = hours_since(e["timestamp"])
        residual = calculate_residual(
            magnitude=e["magnitude_pct"],
            elapsed_hours=elapsed,
            half_life_hours=e["half_life_hours"] or 24,
            confidence=e["chain_confidence"] or 0.5,
            decay_type=e["decay_type"] or "exponential",
        )
        total += residual
        if abs(residual) > 0.01:  # Only include meaningful impacts
            details.append({
                "headline": e["headline"],
                "original": e["magnitude_pct"],
                "residual": round(residual, 3),
                "elapsed_h": round(elapsed, 1),
            })

    return total, details


def calculate_layer2(db: Database, ticker: str) -> tuple[float, list]:
    """Layer 2: Geopolitical risk premiums for this ticker."""
    risks = db.query(
        "SELECT * FROM geopolitical_risks WHERE status!='resolved'")

    total = 0.0
    details = []
    for r in risks:
        affected = json.loads(r["affected_assets"] or "[]")
        premium_map = json.loads(r["risk_premium_json"] or "{}")

        # Check if this ticker is affected
        premium = premium_map.get(ticker)
        if premium is None:
            # Check partial matches (e.g., "방산주" for defense stocks)
            for asset, prem in premium_map.items():
                if ticker.lower() in asset.lower() or asset.lower() in ticker.lower():
                    premium = prem
                    break

        if premium is not None:
            total += premium
            details.append({
                "risk": r["name"],
                "status": r["status"],
                "severity": r["severity"],
                "premium": premium,
            })

    return total, details


def calculate_layer3(db: Database, ticker: str) -> tuple[float, list]:
    """Layer 3: Polymarket probability adjustments."""
    # Check geopolitical risks linked to polymarket events
    risks = db.query(
        "SELECT * FROM geopolitical_risks "
        "WHERE status!='resolved' AND polymarket_ids IS NOT NULL")

    total = 0.0
    details = []
    for r in risks:
        poly_ids = json.loads(r["polymarket_ids"] or "[]")
        for pid in poly_ids:
            # Get latest and previous polymarket price
            latest = db.query_one(
                "SELECT yes_price FROM polymarket_prices "
                "WHERE market_id=? ORDER BY timestamp DESC LIMIT 1", (pid,))
            prev = db.query_one(
                "SELECT yes_price FROM polymarket_prices "
                "WHERE market_id=? ORDER BY timestamp DESC LIMIT 1 OFFSET 12",
                (pid,))  # ~1 hour ago (12 × 5min)

            if latest and prev and latest["yes_price"] and prev["yes_price"]:
                shift = latest["yes_price"] - prev["yes_price"]
                if abs(shift) > 0.02:  # >2pp shift
                    # Adjust Layer 2 premium proportionally
                    premium_map = json.loads(r["risk_premium_json"] or "{}")
                    base_premium = premium_map.get(ticker, 0)
                    adjustment = base_premium * shift * 0.5  # 50% passthrough
                    total += adjustment
                    details.append({
                        "risk": r["name"],
                        "polymarket_id": pid[:12],
                        "prob_shift": round(shift * 100, 1),
                        "adjustment": round(adjustment, 3),
                    })

    return total, details


def get_total_impact(db: Database, ticker: str) -> ImpactResult:
    """Calculate total market impact from all 3 layers."""
    result = ImpactResult(ticker=ticker)

    result.layer1_total, result.layer1_events = calculate_layer1(db, ticker)
    result.layer2_total, result.layer2_risks = calculate_layer2(db, ticker)
    result.layer3_total, result.layer3_details = calculate_layer3(db, ticker)
    result.net_impact = result.layer1_total + result.layer2_total + result.layer3_total

    return result
