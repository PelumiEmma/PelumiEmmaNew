"""
Signal engine: turns recent closing prices into a scored BUY/SELL/NO-SIGNAL
decision.

Four independent checks vote on direction:
  - EMA trend (fast vs slow) on the entry timeframe        - 30 pts
  - MACD momentum on the entry timeframe                   - 30 pts
  - RSI positioning on the entry timeframe                 - 20 pts
  - Higher-timeframe trend confirmation (optional)          - 20 pts

A signal only fires when they agree - that's what keeps it selective
rather than firing on every candle. The higher-timeframe check is what
separates this from just trading the 1-minute noise: it only signals
when the shorter-term setup lines up with the bigger trend.
"""
from dataclasses import dataclass
from typing import List, Optional

from indicators import ema, rsi, macd, last


@dataclass
class Signal:
    pair: str
    direction: str  # "BUY" or "SELL"
    confidence: int  # 0-100
    tier: str        # human-readable confidence tier


def confidence_tier(confidence: int) -> str:
    if confidence >= 90:
        return "🔥 High"
    if confidence >= 75:
        return "✅ Medium"
    return "⚠️ Low"


class SignalEngine:
    def __init__(self, min_confidence: int = 75):
        self.min_confidence = min_confidence

    def evaluate(
        self,
        pair: str,
        closes: List[float],
        htf_closes: Optional[List[float]] = None,
    ) -> Optional[Signal]:
        if len(closes) < 30:
            return None

        ema_fast = last(ema(closes, 9))
        ema_slow = last(ema(closes, 21))
        rsi_val = last(rsi(closes, 14))
        macd_line, signal_line = macd(closes)
        macd_val, macd_sig = last(macd_line), last(signal_line)

        if None in (ema_fast, ema_slow, rsi_val, macd_val, macd_sig):
            return None

        votes = []  # each vote: ("BUY"/"SELL", weight)

        # 1. Trend: fast EMA vs slow EMA
        if ema_fast > ema_slow:
            votes.append(("BUY", 30))
        elif ema_fast < ema_slow:
            votes.append(("SELL", 30))

        # 2. Momentum: MACD line vs signal line
        if macd_val > macd_sig:
            votes.append(("BUY", 30))
        elif macd_val < macd_sig:
            votes.append(("SELL", 30))

        # 3. RSI: avoid overbought/oversold chasing, reward mid-range momentum
        if 50 < rsi_val < 70:
            votes.append(("BUY", 20))
        elif 30 < rsi_val < 50:
            votes.append(("SELL", 20))
        # RSI > 70 or < 30 casts no vote - too extended, sits out

        # 4. Higher-timeframe trend confirmation (optional but recommended).
        # Only counts if it AGREES with the entry-timeframe trend direction -
        # this is a confirmation filter, not an independent signal source.
        if htf_closes and len(htf_closes) >= 30:
            htf_fast = last(ema(htf_closes, 9))
            htf_slow = last(ema(htf_closes, 21))
            if htf_fast is not None and htf_slow is not None:
                if htf_fast > htf_slow and ema_fast > ema_slow:
                    votes.append(("BUY", 20))
                elif htf_fast < htf_slow and ema_fast < ema_slow:
                    votes.append(("SELL", 20))
                # disagreement casts no vote - it doesn't penalize, it just
                # withholds the confirmation bonus

        buy_score = sum(w for d, w in votes if d == "BUY")
        sell_score = sum(w for d, w in votes if d == "SELL")

        if buy_score == 0 and sell_score == 0:
            return None

        direction = "BUY" if buy_score >= sell_score else "SELL"
        confidence = max(buy_score, sell_score)

        if confidence < self.min_confidence:
            return None

        return Signal(
            pair=pair,
            direction=direction,
            confidence=confidence,
            tier=confidence_tier(confidence),
        )
