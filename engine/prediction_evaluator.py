"""Evaluate expired predictions and aggregate agent accuracy."""

import logging
from datetime import datetime

from db import Database

logger = logging.getLogger(__name__)


def evaluate_expired_predictions(db: Database) -> int:
    """Find pending predictions whose evaluation time has passed, score them."""
    now = datetime.now().isoformat()
    pending = db.query(
        "SELECT * FROM predictions WHERE status='pending' AND evaluation_at<=?",
        (now,))

    evaluated = 0
    for pred in pending:
        target_id = pred["target_id"]
        target_type = pred["target_type"]

        # Get actual price at evaluation time
        actual_price = _get_actual_price(db, target_id, target_type)
        if actual_price is None:
            # Mark as skipped if we can't get the price
            db.execute("UPDATE predictions SET status='skipped' WHERE id=?",
                       (pred["id"],))
            continue

        baseline = pred["baseline_price"]
        if baseline is None or baseline == 0:
            db.execute("UPDATE predictions SET status='skipped' WHERE id=?",
                       (pred["id"],))
            continue

        # Calculate actual change
        actual_change = (actual_price - baseline) / baseline * 100

        # Direction check
        predicted_dir = pred["predicted_direction"]
        if actual_change > 0.1:
            actual_dir = "up"
        elif actual_change < -0.1:
            actual_dir = "down"
        else:
            actual_dir = "stable"

        direction_correct = 1 if predicted_dir == actual_dir else 0
        # Give partial credit if predicted stable and actual was small move
        if predicted_dir == "stable" and abs(actual_change) < 1.0:
            direction_correct = 1

        # Median error
        predicted_median = pred["predicted_median_pct"] or 0
        median_error = abs(actual_change - predicted_median)

        # Confidence interval checks
        in_ci70 = 1 if (pred["predicted_ci70_low"] or -999) <= actual_change <= (pred["predicted_ci70_high"] or 999) else 0
        in_ci90 = 1 if (pred["predicted_ci90_low"] or -999) <= actual_change <= (pred["predicted_ci90_high"] or 999) else 0

        # Score: direction(40) + magnitude(30) + calibration(30)
        dir_score = 40 if direction_correct else 0
        mag_score = max(0, 30 - median_error * 10)  # -10 per 1% error
        cal_score = 15 * in_ci70 + 15 * in_ci90
        score = dir_score + mag_score + cal_score

        # Update prediction
        db.execute(
            "UPDATE predictions SET status='evaluated', "
            "actual_price=?, actual_change_pct=?, direction_correct=?, "
            "median_error_pct=?, in_ci70=?, in_ci90=?, score=?, "
            "evaluated_at=datetime('now','localtime') WHERE id=?",
            (actual_price, actual_change, direction_correct,
             median_error, in_ci70, in_ci90, round(score, 1), pred["id"]))

        evaluated += 1
        logger.info("Evaluated: %s %s dir=%s (pred=%s) err=%.2f%% score=%.1f",
                     target_id, pred["agent_role"],
                     actual_dir, predicted_dir, median_error, score)

    if evaluated:
        logger.info("Evaluated %d predictions", evaluated)
        _aggregate_accuracy(db)

    return evaluated


def _get_actual_price(db: Database, target_id: str,
                      target_type: str) -> float | None:
    """Get the latest price for a target, looking at the right table."""
    if target_type in ("stock", "etf", "index"):
        row = db.get_latest_price(target_id)
        return row["price"] if row else None
    elif target_type == "crypto":
        row = db.query_one(
            "SELECT price_krw FROM crypto_prices WHERE symbol=? "
            "ORDER BY timestamp DESC LIMIT 1", (target_id,))
        return row["price_krw"] if row else None
    elif target_type == "polymarket":
        row = db.query_one(
            "SELECT yes_price FROM polymarket_prices WHERE market_id=? "
            "ORDER BY timestamp DESC LIMIT 1", (target_id,))
        return row["yes_price"] * 100 if row else None  # Convert to %
    elif target_type in ("fx", "commodity", "bond"):
        row = db.get_latest_indicator(target_type, target_id)
        return row["value"] if row else None
    return None


def _aggregate_accuracy(db: Database):
    """Aggregate individual predictions into agent_accuracy table."""
    # Get distinct agents with evaluated predictions
    agents = db.query(
        "SELECT DISTINCT agent_role FROM predictions WHERE status='evaluated'")

    now = datetime.now()
    period = now.strftime("%Y-W%V")  # ISO week

    for agent_row in agents:
        agent = agent_row["agent_role"]

        # Get recent evaluated predictions (last 30 days)
        preds = db.query(
            "SELECT * FROM predictions WHERE agent_role=? AND status='evaluated' "
            "AND evaluated_at>datetime('now','localtime','-30 days')",
            (agent,))

        if not preds:
            continue

        total = len(preds)
        dir_correct = sum(1 for p in preds if p["direction_correct"] == 1)
        dir_rate = dir_correct / total if total > 0 else 0

        errors = [p["median_error_pct"] for p in preds if p["median_error_pct"] is not None]
        avg_error = sum(errors) / len(errors) if errors else 0

        ci70_hits = sum(1 for p in preds if p["in_ci70"] == 1)
        ci90_hits = sum(1 for p in preds if p["in_ci90"] == 1)
        ci70_rate = ci70_hits / total if total > 0 else 0
        ci90_rate = ci90_hits / total if total > 0 else 0

        # Systematic bias: mean signed error
        signed_errors = []
        for p in preds:
            if p["actual_change_pct"] is not None and p["predicted_median_pct"] is not None:
                signed_errors.append(p["predicted_median_pct"] - p["actual_change_pct"])
        bias = sum(signed_errors) / len(signed_errors) if signed_errors else 0

        # Calibration: how well does confidence match actual hit rate?
        # Group by confidence buckets
        confidence_buckets = {}
        for p in preds:
            conf = p["confidence"] or 50
            bucket = (conf // 20) * 20  # 0-19, 20-39, 40-59, 60-79, 80-100
            if bucket not in confidence_buckets:
                confidence_buckets[bucket] = {"total": 0, "correct": 0}
            confidence_buckets[bucket]["total"] += 1
            if p["direction_correct"] == 1:
                confidence_buckets[bucket]["correct"] += 1

        # Calibration error: average |expected_rate - actual_rate| per bucket
        cal_errors = []
        for bucket, stats in confidence_buckets.items():
            expected_rate = (bucket + 10) / 100  # midpoint of bucket
            actual_rate = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
            cal_errors.append(abs(expected_rate - actual_rate))
        calibration = 1 - (sum(cal_errors) / len(cal_errors) if cal_errors else 0)

        # Ensemble weight based on recent accuracy
        weight = dir_rate * (1 + calibration) / 2

        # Upsert
        db.execute(
            "INSERT OR REPLACE INTO agent_accuracy "
            "(agent_role, period, regime, total_predictions, direction_correct, "
            "direction_rate, avg_median_error, ci70_hit_rate, ci90_hit_rate, "
            "calibration_score, systematic_bias, ensemble_weight, updated_at) "
            "VALUES (?, ?, 'all', ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))",
            (agent, period, total, dir_correct, round(dir_rate, 4),
             round(avg_error, 4), round(ci70_rate, 4), round(ci90_rate, 4),
             round(calibration, 4), round(bias, 4), round(weight, 4)))

        logger.info("Agent %s accuracy: dir=%.1f%% cal=%.2f bias=%+.2f weight=%.2f",
                     agent, dir_rate * 100, calibration, bias, weight)
