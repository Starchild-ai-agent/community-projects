import io
import base64

import matplotlib

matplotlib.use("Agg")  # headless rendering; must precede pyplot import

import matplotlib.pyplot as plt
import pandas as pd
import mplfinance as mpf

from . import config


class ChartRenderer:
    def render(self, candles: list[dict], title: str = "") -> str:
        """Render candles to a base64-encoded PNG for vision model input."""
        if len(candles) < 5:
            return ""

        df = pd.DataFrame(candles)
        df["Date"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("Date", inplace=True)
        df.rename(columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }, inplace=True)

        buf = io.BytesIO()
        mpf.plot(
            df,
            type="candle",
            volume=True,
            style="yahoo",
            title=title,
            figsize=(12, 7),
            savefig=dict(fname=buf, dpi=150, bbox_inches="tight"),
        )
        plt.close("all")
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")

    def render_with_indicators(
        self,
        candles: list[dict],
        features_list: list[dict],
        title: str = "",
    ) -> str:
        """Render candles with RSI panel overlay."""
        if len(candles) < 5:
            return ""

        df = pd.DataFrame(candles)
        df["Date"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("Date", inplace=True)
        df.rename(columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }, inplace=True)

        addplots = []

        # RSI panel
        if features_list and len(features_list) == len(df):
            rsi_vals = [f.get("rsi") for f in features_list]
            if any(v is not None for v in rsi_vals):
                rsi_series = pd.Series(rsi_vals, index=df.index, dtype=float)
                addplots.append(
                    mpf.make_addplot(rsi_series, panel=2, ylabel="RSI", color="purple")
                )

            # EMA overlays
            ema_fast = [f.get("ema_fast") for f in features_list]
            if any(v is not None for v in ema_fast):
                addplots.append(
                    mpf.make_addplot(
                        pd.Series(ema_fast, index=df.index, dtype=float),
                        color="orange", width=0.7,
                    )
                )

            ema_slow = [f.get("ema_slow") for f in features_list]
            if any(v is not None for v in ema_slow):
                addplots.append(
                    mpf.make_addplot(
                        pd.Series(ema_slow, index=df.index, dtype=float),
                        color="blue", width=0.7,
                    )
                )

            # Bollinger Bands
            bb_upper = [f.get("bb_upper") for f in features_list]
            bb_lower = [f.get("bb_lower") for f in features_list]
            if any(v is not None for v in bb_upper):
                addplots.append(
                    mpf.make_addplot(
                        pd.Series(bb_upper, index=df.index, dtype=float),
                        color="gray", linestyle="--", width=0.5,
                    )
                )
                addplots.append(
                    mpf.make_addplot(
                        pd.Series(bb_lower, index=df.index, dtype=float),
                        color="gray", linestyle="--", width=0.5,
                    )
                )

        buf = io.BytesIO()
        kwargs = dict(
            type="candle",
            volume=True,
            style="yahoo",
            title=title,
            figsize=(12, 8),
            savefig=dict(fname=buf, dpi=150, bbox_inches="tight"),
        )
        if addplots:
            kwargs["addplot"] = addplots

        mpf.plot(df, **kwargs)
        plt.close("all")
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")
