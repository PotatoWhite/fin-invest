"""Initialize database with schema and seed model_params with defaults."""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from db import Database


def seed_model_params(db: Database):
    """Seed model_params with initial values."""

    params = [
        # Half-life defaults (hours)
        ("half_life", "earnings_surprise_risk_on", 168, "5-10 days in hours"),
        ("half_life", "earnings_surprise_risk_off", 240, "7-14 days in hours"),
        ("half_life", "fomc_risk_on", 3, "2-4 hours"),
        ("half_life", "fomc_risk_off", 6, "4-8 hours"),
        ("half_life", "cpi_employment_risk_on", 6, "4-8 hours"),
        ("half_life", "cpi_employment_risk_off", 12, "8-16 hours"),
        ("half_life", "geopolitical_risk_on", 4, "2-6 hours"),
        ("half_life", "geopolitical_risk_off", 48, "1-3 days"),
        ("half_life", "tariff_trade_risk_on", 48, "1-3 days"),
        ("half_life", "tariff_trade_risk_off", 120, "3-7 days"),
        ("half_life", "sns_meme_risk_on", 2, "1-4 hours"),
        ("half_life", "sns_meme_risk_off", 4, "2-6 hours"),
        ("half_life", "regulation_risk_on", 120, "3-7 days"),
        ("half_life", "regulation_risk_off", 240, "7-14 days"),

        # Impact magnitude multipliers
        ("impact_magnitude", "regime_sensitivity_risk_on", 0.5, "Dampened in risk-on"),
        ("impact_magnitude", "regime_sensitivity_risk_off", 2.0, "Amplified in risk-off"),
        ("impact_magnitude", "regime_sensitivity_transition", 1.5, "Moderate"),
        ("impact_magnitude", "positioning_max_amplifier", 3.0, "Max positioning effect"),
        ("impact_magnitude", "liquidity_max_amplifier", 2.0, "Max liquidity effect"),

        # Regime detection thresholds
        ("regime", "score_risk_on", 0.7, "Above = Risk-On"),
        ("regime", "score_transition", 0.4, "Above = Transition"),
        ("regime", "score_risk_off", 0.15, "Above = Risk-Off, below = Crisis"),
        ("regime", "vix_weight", 0.35, "VIX contribution to regime score"),
        ("regime", "spread_weight", 0.25, "HY spread contribution"),
        ("regime", "breadth_weight", 0.20, "Market breadth contribution"),
        ("regime", "flow_weight", 0.20, "Safe haven flow contribution"),

        # Signal filter thresholds
        ("signal_filter", "volume_min_multiplier", 1.0, "Min volume vs 20d avg"),
        ("signal_filter", "breadth_min_ratio", 0.5, "Min advance/decline ratio"),
        ("signal_filter", "quality_tier2_threshold", 0.7, "Tier 2 alert threshold"),
        ("signal_filter", "quality_ignore_threshold", 0.4, "Below = discard"),

        # Technical indicator parameters
        ("technical", "sma_short", 20, "Short SMA period"),
        ("technical", "sma_medium", 50, "Medium SMA period"),
        ("technical", "sma_long", 200, "Long SMA period"),
        ("technical", "rsi_period", 14, "RSI calculation period"),
        ("technical", "macd_fast", 12, "MACD fast EMA"),
        ("technical", "macd_slow", 26, "MACD slow EMA"),
        ("technical", "macd_signal", 9, "MACD signal line"),
        ("technical", "bollinger_period", 20, "Bollinger Bands period"),
        ("technical", "bollinger_std", 2.0, "Bollinger Bands std dev"),

        # Position sizing
        ("position_sizing", "max_single_position_pct", 20.0, "Max 20% per ticker"),
        ("position_sizing", "min_cash_pct", 15.0, "Min 15% cash"),
        ("position_sizing", "max_loss_per_trade_pct", 2.0, "Max 2% loss per trade"),
        ("position_sizing", "kelly_fraction", 0.5, "Half-Kelly"),
    ]

    count = 0
    for category, param_name, value, description in params:
        db.insert(
            "model_params",
            category=category,
            param_name=param_name,
            value=value,
            description=description,
        )
        count += 1

    print(f"Seeded {count} model parameters")


def seed_goguma_cash(db: Database):
    """Initialize goguma's starting capital: 1억원."""
    db.insert("goguma_cash", currency="KRW", amount=100_000_000)
    print("Goguma initialized: ₩100,000,000")


if __name__ == "__main__":
    db = Database()
    print(f"DB: {db.db_path}")
    print(f"Size: {db.db_size_mb():.2f} MB")
    print(f"Tables: {db.table_counts()}")

    seed_model_params(db)
    seed_goguma_cash(db)

    print("Initialization complete!")
    print(f"Size: {db.db_size_mb():.2f} MB")
