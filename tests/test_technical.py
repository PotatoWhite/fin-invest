"""Tests for engine/technical.py."""

import pytest
from engine.technical import (
    compute_sma, compute_ema, compute_rsi, compute_macd,
    compute_bollinger, compute_atr, compute_volatility,
    determine_trend, compute_all,
)


def _make_prices(n=60, base=100, step=0.5):
    """Generate uptrending price series."""
    return [base + i * step for i in range(n)]


def _make_flat_prices(n=60, value=100):
    return [value] * n


class TestSMA:
    def test_sma_20(self):
        prices = _make_prices(30)
        result = compute_sma(prices, 20)
        assert result is not None
        assert 100 < result < 115

    def test_sma_insufficient_data(self):
        assert compute_sma([1, 2, 3], 20) is None

    def test_sma_exact_period(self):
        prices = [10.0] * 20
        assert compute_sma(prices, 20) == 10.0


class TestEMA:
    def test_ema_basic(self):
        prices = _make_prices(30)
        result = compute_ema(prices, 12)
        assert result is not None

    def test_ema_insufficient(self):
        assert compute_ema([1, 2], 12) is None


class TestRSI:
    def test_rsi_uptrend(self):
        prices = _make_prices(30)
        rsi = compute_rsi(prices)
        assert rsi is not None
        assert rsi > 50  # Uptrend should have RSI > 50

    def test_rsi_downtrend(self):
        prices = list(reversed(_make_prices(30)))
        rsi = compute_rsi(prices)
        assert rsi is not None
        assert rsi < 50

    def test_rsi_flat(self):
        prices = _make_flat_prices(30)
        rsi = compute_rsi(prices)
        # All gains=0, all losses=0 → RSI=100
        assert rsi == 100.0


class TestMACD:
    def test_macd_basic(self):
        prices = _make_prices(40)
        macd, signal, hist = compute_macd(prices)
        assert macd is not None

    def test_macd_insufficient(self):
        macd, signal, hist = compute_macd([1, 2, 3])
        assert macd is None


class TestBollinger:
    def test_bollinger_basic(self):
        prices = _make_prices(30)
        upper, middle, lower = compute_bollinger(prices)
        assert upper is not None
        assert middle is not None
        assert lower is not None
        assert upper > middle > lower

    def test_bollinger_flat(self):
        prices = _make_flat_prices(30)
        upper, middle, lower = compute_bollinger(prices)
        assert upper == middle == lower == 100.0


class TestATR:
    def test_atr_basic(self):
        highs = [101 + i * 0.5 for i in range(30)]
        lows = [99 + i * 0.5 for i in range(30)]
        closes = [100 + i * 0.5 for i in range(30)]
        atr = compute_atr(highs, lows, closes)
        assert atr is not None
        assert atr > 0


class TestVolatility:
    def test_volatility_uptrend(self):
        prices = _make_prices(30)
        vol = compute_volatility(prices)
        assert vol is not None
        assert vol > 0

    def test_volatility_flat(self):
        prices = _make_flat_prices(30)
        vol = compute_volatility(prices)
        assert vol == 0.0


class TestTrend:
    def test_bullish(self):
        prices = _make_prices(60)
        assert determine_trend(prices) == "bullish"

    def test_bearish(self):
        prices = list(reversed(_make_prices(60)))
        assert determine_trend(prices) == "bearish"


class TestComputeAll:
    def test_full_compute(self):
        prices = _make_prices(60)
        result = compute_all("TEST", prices)
        assert result.ticker == "TEST"
        assert result.data_points == 60
        assert result.sma_20 is not None
        assert result.sma_50 is not None
        assert result.rsi_14 is not None
        assert result.trend == "bullish"
