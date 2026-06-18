from streaming_indicators import RSI, EMA, BBands, ATR


class FeatureEngine:
    def __init__(self):
        self._indicators = {}

    def _get(self, symbol: str, timeframe: str):
        key = f"{symbol}:{timeframe}"
        if key not in self._indicators:
            self._indicators[key] = {
                "rsi": RSI(period=14),
                "ema_fast": EMA(period=9),
                "ema_slow": EMA(period=21),
                "ema_trend": EMA(period=50),
                "bb": BBands(period=20, stddev_mult=2),
                "atr": ATR(period=14),
                "prev_ema_spread": None,
            }
        return self._indicators[key]

    def update(self, symbol: str, timeframe: str, candle: dict) -> dict:
        ind = self._get(symbol, timeframe)
        close = candle["close"]
        high = candle["high"]
        low = candle["low"]

        rsi_val = ind["rsi"].update(close)
        ema_fast = ind["ema_fast"].update(close)
        ema_slow = ind["ema_slow"].update(close)
        ema_trend = ind["ema_trend"].update(close)
        atr_val = ind["atr"].update(candle)

        bb_result = ind["bb"].update(close)
        bb_upper = bb_mid = bb_lower = bb_position = None
        if bb_result and bb_result[0] is not None:
            bb_upper, bb_mid, bb_lower = bb_result
            bb_range = bb_upper - bb_lower
            if bb_range > 0:
                bb_position = (close - bb_lower) / bb_range

        # ema_cross is the fast/slow spread; ema_cross_signal fires only on an
        # actual crossover (the spread changing sign between candles).
        ema_cross = None
        ema_cross_signal = None
        if ema_fast is not None and ema_slow is not None:
            ema_cross = ema_fast - ema_slow
            prev_spread = ind["prev_ema_spread"]
            if prev_spread is not None:
                if prev_spread <= 0 < ema_cross:
                    ema_cross_signal = "golden_cross"
                elif prev_spread >= 0 > ema_cross:
                    ema_cross_signal = "death_cross"
            ind["prev_ema_spread"] = ema_cross

        trend = None
        if ema_trend is not None:
            if close > ema_trend:
                trend = "above_ema50"
            else:
                trend = "below_ema50"

        return {
            "rsi": rsi_val,
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "ema_trend": ema_trend,
            "ema_cross": ema_cross,
            "ema_cross_signal": ema_cross_signal,
            "bb_upper": bb_upper,
            "bb_mid": bb_mid,
            "bb_lower": bb_lower,
            "bb_position": bb_position,
            "atr": atr_val,
            "trend": trend,
            "close": close,
            "volume": candle["volume"],
        }
