"""
Market regime detection.

Classifies the current market into one of:
- trending_up: sustained directional move upward
- trending_down: sustained directional move downward
- range: price oscillating between support and resistance
- high_vol: sudden expansion in volatility (breakout or crash)
- low_vol: compression / squeeze (pre-breakout)

Adapts Tier 1 behavior:
- trending: favor momentum signals, ignore mean-reversion
- range: favor mean-reversion, ignore breakout fakes
- high_vol: widen thresholds, reduce position sizes
- low_vol: tighten thresholds, watch for breakout
"""

from collections import deque


class RegimeDetector:
    def __init__(self, lookback: int = 50):
        self.lookback = lookback
        self._regimes: dict[str, str] = {}  # symbol:timeframe → regime

    def detect(self, symbol: str, timeframe: str, candles: list[dict], features: dict) -> str:
        """Classify current market regime from recent candle history."""
        if len(candles) < self.lookback:
            return "unknown"

        recent = candles[-self.lookback:]
        closes = [c["close"] for c in recent]
        highs = [c["high"] for c in recent]
        lows = [c["low"] for c in recent]

        # ── Trend detection via linear regression slope ──
        n = len(closes)
        x_mean = (n - 1) / 2
        y_mean = sum(closes) / n
        numerator = sum((i - x_mean) * (closes[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator else 0

        # Normalize slope as percentage of price
        slope_pct = (slope / y_mean) * 100 if y_mean else 0

        # ── Volatility via ATR ratio ──
        atr = features.get("atr")
        if atr and y_mean > 0:
            atr_pct = (atr / y_mean) * 100
        else:
            # Manual ATR approximation
            ranges = [highs[i] - lows[i] for i in range(len(recent))]
            avg_range = sum(ranges) / len(ranges) if ranges else 0
            atr_pct = (avg_range / y_mean) * 100 if y_mean else 0

        # ── Choppiness via Kaufman efficiency ratio ──
        # net displacement / total path length: ~1 = clean trend, ~0 = chop.
        net_move = abs(closes[-1] - closes[0])
        path = sum(abs(closes[i + 1] - closes[i]) for i in range(n - 1))
        efficiency = net_move / path if path > 0 else 0.0

        # ── Bollinger Band width for squeeze detection ──
        bb_upper = features.get("bb_upper")
        bb_lower = features.get("bb_lower")
        bb_mid = features.get("bb_mid")
        bb_width_pct = None
        if bb_upper and bb_lower and bb_mid and bb_mid > 0:
            bb_width_pct = ((bb_upper - bb_lower) / bb_mid) * 100

        # ── Classification ──
        regime = self._classify(slope_pct, atr_pct, efficiency, bb_width_pct)

        key = f"{symbol}:{timeframe}"
        self._regimes[key] = regime
        return regime

    def _classify(self, slope_pct, atr_pct, efficiency, bb_width_pct) -> str:
        # High volatility override
        if atr_pct > 3.0:
            return "high_vol"

        # Low volatility / squeeze
        if bb_width_pct is not None and bb_width_pct < 2.0:
            return "low_vol"
        if atr_pct < 0.8:
            return "low_vol"

        # Strong trend: needs both directional slope and an efficient path
        if efficiency > 0.3:
            if slope_pct > 0.15:
                return "trending_up"
            if slope_pct < -0.15:
                return "trending_down"

        # Choppy price action regardless of drift = range
        if efficiency < 0.25:
            return "range"

        # Mild trend
        if slope_pct > 0.05:
            return "trending_up"
        if slope_pct < -0.05:
            return "trending_down"

        return "range"

    def get(self, symbol: str, timeframe: str) -> str:
        return self._regimes.get(f"{symbol}:{timeframe}", "unknown")

    def adjust_screen_score(self, regime: str, base_score: float, features: dict) -> float:
        """
        Adjust Tier 1 screening score based on regime.
        This is how the system adapts its behavior to market conditions.
        """
        rsi = features.get("rsi")
        bb_pos = features.get("bb_position")

        if regime == "trending_up":
            # Favor momentum, penalize overbought signals less
            if rsi is not None and rsi > 60:
                base_score += 0.1  # momentum is good in uptrend
            if bb_pos is not None and bb_pos < 0.2:
                base_score += 0.15  # pullback to lower band in uptrend = buy
            if rsi is not None and rsi < 30:
                base_score -= 0.1  # oversold in uptrend might be trend break, careful

        elif regime == "trending_down":
            if rsi is not None and rsi < 40:
                base_score += 0.1
            if bb_pos is not None and bb_pos > 0.8:
                base_score += 0.15  # rally to upper band in downtrend = sell
            if rsi is not None and rsi > 70:
                base_score -= 0.1

        elif regime == "range":
            # Favor mean-reversion at extremes
            if bb_pos is not None and (bb_pos > 0.9 or bb_pos < 0.1):
                base_score += 0.2
            # Penalize crossover events (likely fakeouts in a range)
            if features.get("ema_cross_signal"):
                base_score -= 0.1

        elif regime == "high_vol":
            # Be more selective, require stronger signals
            base_score *= 0.8

        elif regime == "low_vol":
            # Watch for breakout, Bollinger squeeze
            if bb_pos is not None and (bb_pos > 0.95 or bb_pos < 0.05):
                base_score += 0.25  # breakout from squeeze

        return max(0.0, min(1.0, base_score))
