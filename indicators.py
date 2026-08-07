"""
Lightweight technical indicators - no external TA library required.
All functions take a list of floats (closing prices, oldest -> newest)
and return a list/float aligned to the input.
"""
from typing import List, Optional


def ema(values: List[float], period: int) -> List[Optional[float]]:
    if len(values) < period:
        return [None] * len(values)
    k = 2 / (period + 1)
    out: List[Optional[float]] = [None] * (period - 1)
    seed = sum(values[:period]) / period
    out.append(seed)
    prev = seed
    for price in values[period:]:
        val = price * k + prev * (1 - k)
        out.append(val)
        prev = val
    return out


def rsi(values: List[float], period: int = 14) -> List[Optional[float]]:
    if len(values) <= period:
        return [None] * len(values)
    gains, losses = [], []
    for i in range(1, len(values)):
        diff = values[i] - values[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    out: List[Optional[float]] = [None] * period
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    rs = avg_gain / avg_loss if avg_loss != 0 else float("inf")
    out.append(100 - (100 / (1 + rs)))

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else float("inf")
        out.append(100 - (100 / (1 + rs)))
    return out


def macd(values: List[float], fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = ema(values, fast)
    ema_slow = ema(values, slow)
    macd_line = [
        (f - s) if (f is not None and s is not None) else None
        for f, s in zip(ema_fast, ema_slow)
    ]
    clean = [v for v in macd_line if v is not None]
    if len(clean) < signal:
        return macd_line, [None] * len(values)
    signal_seed = ema(clean, signal)
    # re-align signal line to full length (pad the front with None)
    pad = len(macd_line) - len(signal_seed)
    signal_line = [None] * pad + signal_seed
    return macd_line, signal_line


def last(values):
    """Return the last non-None value, or None."""
    for v in reversed(values):
        if v is not None:
            return v
    return None
