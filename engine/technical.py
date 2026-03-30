"""Technical indicators computed from stored OHLCV data."""

import math
from dataclasses import dataclass


@dataclass
class TechnicalResult:
    ticker: str
    data_points: int
    current_price: float | None = None
    sma_20: float | None = None
    sma_50: float | None = None
    sma_100: float | None = None
    sma_200: float | None = None
    ema_12: float | None = None
    ema_26: float | None = None
    rsi_14: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
    bollinger_upper: float | None = None
    bollinger_middle: float | None = None
    bollinger_lower: float | None = None
    atr_14: float | None = None
    volatility: float | None = None  # std dev of daily returns
    trend: str = "neutral"  # bullish, bearish, neutral


def compute_sma(prices: list[float], period: int) -> float | None:
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


def compute_ema(prices: list[float], period: int) -> float | None:
    if len(prices) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return ema


def compute_rsi(prices: list[float], period: int = 14) -> float | None:
    if len(prices) < period + 1:
        return None
    gains, losses = [], []
    for i in range(-period, 0):
        diff = prices[i] - prices[i - 1]
        gains.append(max(0, diff))
        losses.append(max(0, -diff))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def compute_macd(prices: list[float]) -> tuple[float | None, float | None, float | None]:
    """Returns (macd_line, signal_line, histogram)."""
    ema12 = compute_ema(prices, 12)
    ema26 = compute_ema(prices, 26)
    if ema12 is None or ema26 is None:
        return None, None, None
    macd_line = ema12 - ema26

    # Signal line: 9-period EMA of MACD values
    # Approximate by computing MACD for last 35 periods
    if len(prices) < 35:
        return macd_line, None, None

    macd_values = []
    for i in range(35, len(prices) + 1):
        subset = prices[:i]
        e12 = compute_ema(subset, 12)
        e26 = compute_ema(subset, 26)
        if e12 and e26:
            macd_values.append(e12 - e26)

    if len(macd_values) >= 9:
        signal = compute_ema(macd_values, 9)
        histogram = macd_line - signal if signal else None
        return macd_line, signal, histogram

    return macd_line, None, None


def compute_bollinger(prices: list[float], period: int = 20,
                      num_std: float = 2.0) -> tuple[float | None, float | None, float | None]:
    """Returns (upper, middle, lower)."""
    if len(prices) < period:
        return None, None, None
    window = prices[-period:]
    middle = sum(window) / period
    variance = sum((p - middle) ** 2 for p in window) / period
    std = math.sqrt(variance)
    return (
        round(middle + num_std * std, 2),
        round(middle, 2),
        round(middle - num_std * std, 2),
    )


def compute_atr(highs: list[float], lows: list[float], closes: list[float],
                period: int = 14) -> float | None:
    """Average True Range."""
    if len(closes) < period + 1:
        return None
    true_ranges = []
    for i in range(-period, 0):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        true_ranges.append(tr)
    return sum(true_ranges) / period


def compute_volatility(prices: list[float], period: int = 20) -> float | None:
    """Standard deviation of daily returns."""
    if len(prices) < period + 1:
        return None
    returns = []
    for i in range(-period, 0):
        if prices[i - 1] != 0:
            returns.append((prices[i] - prices[i - 1]) / prices[i - 1])
    if not returns:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    return math.sqrt(variance)


def determine_trend(prices: list[float]) -> str:
    sma20 = compute_sma(prices, 20)
    sma50 = compute_sma(prices, 50)
    if sma20 is None or sma50 is None:
        return "neutral"
    current = prices[-1]
    if current > sma20 > sma50:
        return "bullish"
    if current < sma20 < sma50:
        return "bearish"
    return "neutral"


def compute_all(ticker: str, closes: list[float],
                highs: list[float] | None = None,
                lows: list[float] | None = None) -> TechnicalResult:
    """Compute all technical indicators for a ticker."""
    result = TechnicalResult(ticker=ticker, data_points=len(closes))

    if not closes:
        return result

    result.current_price = closes[-1]
    result.sma_20 = compute_sma(closes, 20)
    result.sma_50 = compute_sma(closes, 50)
    result.sma_100 = compute_sma(closes, 100)
    result.sma_200 = compute_sma(closes, 200)
    result.ema_12 = compute_ema(closes, 12)
    result.ema_26 = compute_ema(closes, 26)
    result.rsi_14 = compute_rsi(closes, 14)

    macd, signal, hist = compute_macd(closes)
    result.macd = round(macd, 4) if macd else None
    result.macd_signal = round(signal, 4) if signal else None
    result.macd_histogram = round(hist, 4) if hist else None

    upper, middle, lower = compute_bollinger(closes)
    result.bollinger_upper = upper
    result.bollinger_middle = middle
    result.bollinger_lower = lower

    if highs and lows:
        result.atr_14 = compute_atr(highs, lows, closes, 14)

    result.volatility = compute_volatility(closes)
    result.trend = determine_trend(closes)

    return result
