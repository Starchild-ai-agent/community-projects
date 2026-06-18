"""
Tiered analysis loop.

Tier 1: Fast screen on EVERY candle close (<1ms). Rule-based heuristics
        filter out ~90% of candles as uninteresting.
Tier 2: LLM multimodal analysis (2-10s). Only fires when Tier 1 flags
        a setup. Sends chart image + structured data (VISTA/FinAgent pattern).
Tier 3: Signal emission. Fires callbacks with the analysis result.

Research basis:
- FinAgent: multimodal (chart + OHLCV + indicators) → +36% profit
- VISTA: vision-language chart analysis → +89.8% vs text-only
- AI-Trader: tiered approach avoids LLM latency bottleneck
- TradingAgents: multi-timeframe confirmation
- Janus-Q: news as primary decision unit → +102% Sharpe ratio
"""

import asyncio
import time
from collections import deque
from typing import Callable

from . import config
from .stream import CandleBuffer
from .features import FeatureEngine
from .charts import ChartRenderer
from .memory import AnalysisMemory
from .llm_client import LLMClient
from .news import NewsFeed
from .research import BraveResearcher
from .outcomes import OutcomeTracker, parse_price_level
from .portfolio import Portfolio
from .derivatives import DerivativesData
from .self_tune import SelfTuner
from .regime import RegimeDetector


class AnalysisLoop:
    def __init__(
        self,
        features: FeatureEngine,
        charts: ChartRenderer,
        llm: LLMClient,
        memory: AnalysisMemory,
        news: NewsFeed = None,
        researcher: BraveResearcher = None,
        outcomes: OutcomeTracker = None,
        portfolio: Portfolio = None,
        derivatives: DerivativesData = None,
        self_tuner: SelfTuner = None,
    ):
        self.features = features
        self.charts = charts
        self.llm = llm
        self.memory = memory
        self.news = news
        self.researcher = researcher
        self.outcomes = outcomes
        self.portfolio = portfolio
        self.derivatives = derivatives
        self.self_tuner = self_tuner
        self.regime = RegimeDetector()
        self.signal_callbacks: list[Callable] = []
        self.dashboard = None  # set externally

        # Track features per symbol/tf for chart overlay
        self._features_history: dict[str, deque] = {}

        # Cooldown: prevent spamming LLM calls
        self._last_analysis: dict[str, float] = {}

    def warmup(self, symbol: str, timeframe: str, candles: list[dict]):
        """Feed historical candles through features engine to warm up indicators.

        The last candle from fetch_ohlcv is still forming — skip it; the live
        stream will deliver its final values when it closes.
        """
        hist_key = f"{symbol}:{timeframe}"
        if hist_key not in self._features_history:
            self._features_history[hist_key] = deque(maxlen=config.BUFFER_SIZE)

        closed = candles[:-1]
        for c in closed:
            feat = self.features.update(symbol, timeframe, c)
            self._features_history[hist_key].append(feat)

        # Mark to market once with the latest price; never run exit checks
        # against historical prices
        if self.portfolio and candles:
            self.portfolio.update_prices(
                {symbol: candles[-1]["close"]}, check_exits=False
            )

        count = len(self._features_history[hist_key])
        print(f"[WARMUP] {symbol} {timeframe}: {count} features computed")

    async def on_candle(self, symbol: str, timeframe: str, buffer: CandleBuffer):
        candles = list(buffer.timeframes[timeframe])
        # candles[-1] is the candle that just OPENED (still forming) — the one
        # that just closed with final OHLCV is candles[-2]. Indicators and
        # screening run on closed candles only; the forming candle's close is
        # used as the freshest live price for mark-to-market.
        if len(candles) < 21:
            return

        closed_candles = candles[:-1]
        closed = closed_candles[-1]
        live_price = candles[-1]["close"]

        feat = self.features.update(symbol, timeframe, closed)

        # ── PORTFOLIO UPDATE: mark-to-market + stop/target/max-hold exits ──
        if self.portfolio:
            exits = self.portfolio.update_prices({symbol: live_price})
            for ex in exits:
                print(f"[EXIT] {ex['side'].upper()} {ex['symbol']} closed "
                      f"({ex['reason']}) @ {ex['exit_price']:.2f} "
                      f"P&L ${ex['pnl']:+.2f}")

        # ── OUTCOME CHECK: on every candle, check pending signals ──
        # This is the feedback loop — runs before analysis so new
        # reflections are available for the next Tier 2 call
        if self.outcomes:
            self.outcomes.check_outcomes(symbol, live_price)

        # ── SELF-TUNE: periodically review and adjust parameters ──
        if self.self_tuner:
            self.self_tuner.maybe_review()

        # Track features for chart rendering
        hist_key = f"{symbol}:{timeframe}"
        if hist_key not in self._features_history:
            self._features_history[hist_key] = deque(maxlen=config.BUFFER_SIZE)
        self._features_history[hist_key].append(feat)

        # ── REGIME DETECTION ──
        current_regime = self.regime.detect(symbol, timeframe, closed_candles, feat)

        # ── TIER 1: Fast screen (regime-adjusted) ──
        score = self._fast_screen(feat, closed_candles)
        score = self.regime.adjust_screen_score(current_regime, score, feat)
        if score < config.SCREEN_THRESHOLD:
            return

        # Cooldown is per SYMBOL, not per symbol:timeframe — one volume spike
        # would otherwise trigger parallel LLM calls from 1m, 5m and 15m at once
        now = time.time()
        last = self._last_analysis.get(symbol, 0)
        if now - last < config.ANALYSIS_COOLDOWN:
            return
        self._last_analysis[symbol] = now

        # ── PRE-CHECK: skip LLM if all directions would be risk-blocked ──
        if self.portfolio:
            buy_check = self.portfolio.check_risk(symbol, "BUY", 50)
            sell_check = self.portfolio.check_risk(symbol, "SELL", 50)
            if not buy_check["allowed"] and not sell_check["allowed"]:
                return  # both directions blocked, no point calling LLM

        print(
            f"[T1] {symbol} {timeframe} score={score:.2f} regime={current_regime}"
            f" — escalating to Tier 2"
        )

        # Push to dashboard
        if self.dashboard:
            asyncio.create_task(
                self.dashboard.push_tier1(symbol, timeframe, score, current_regime)
            )

        # ── TIER 2: LLM multimodal analysis ──
        analysis = await self._llm_analyze(
            symbol, timeframe, closed_candles, feat, live_price
        )
        if not analysis:
            return

        print(
            f"[T2] {symbol} {timeframe}: {analysis.get('action')} "
            f"strength={analysis.get('signal_strength')} "
            f"trend={analysis.get('trend')}"
        )

        # Store in memory
        self.memory.store(symbol, timeframe, analysis)

        # ── RISK GATE: check portfolio constraints before emitting ──
        action = analysis.get("action", "HOLD")
        if action != "HOLD" and self.portfolio:
            risk_check = self.portfolio.check_risk(
                symbol, action, analysis.get("signal_strength", 0)
            )
            if not risk_check["allowed"]:
                print(f"[RISK] {symbol} {action} BLOCKED: {risk_check['reason']}")
                analysis["action"] = "HOLD"
                analysis["reasoning"] += f" [RISK BLOCKED: {risk_check['reason']}]"
                action = "HOLD"
            else:
                analysis["suggested_size"] = risk_check["suggested_size"]

        # ── TIER 3: Signal emission + outcome tracking ──
        if action != "HOLD":
            # Open virtual position with the LLM's own risk levels attached:
            # invalidation → stop, opposite key level → target
            if self.portfolio:
                side = "long" if action == "BUY" else "short"
                stop, target = self._extract_levels(analysis, action, live_price)
                self.portfolio.open_position(
                    symbol, side, live_price,
                    analysis.get("suggested_size", 0),
                    stop=stop, target=target,
                )

            # Start tracking this signal's outcome
            if self.outcomes:
                self.outcomes.record_signal(
                    symbol, timeframe, analysis, live_price
                )
            await self._emit_signal(symbol, timeframe, analysis)

    @staticmethod
    def _extract_levels(analysis: dict, action: str, entry: float):
        """Derive stop (from invalidation) and target (from key levels),
        sanity-checked to sit on the correct side of the entry price."""
        stop = parse_price_level(analysis.get("invalidation"), reference=entry)
        levels = analysis.get("key_levels") or {}
        if action == "BUY":
            target = parse_price_level(levels.get("resistance"), reference=entry)
            if stop is not None and stop >= entry:
                stop = None
            if target is not None and target <= entry:
                target = None
        else:
            target = parse_price_level(levels.get("support"), reference=entry)
            if stop is not None and stop <= entry:
                stop = None
            if target is not None and target >= entry:
                target = None
        return stop, target

    def _fast_screen(self, features: dict, candles: list[dict]) -> float:
        """
        Tier 1: sub-millisecond rule-based screening.
        Returns 0.0–1.0 interestingness score.

        RSI extremes and BB-band touches describe the same "price stretched"
        event, so they share one capped contribution rather than stacking to
        the threshold on their own.
        """
        score = 0.0

        # Price stretched: RSI extreme and/or BB band touch
        stretched = 0
        rsi = features.get("rsi")
        if rsi is not None and (rsi > config.RSI_OVERBOUGHT or rsi < config.RSI_OVERSOLD):
            stretched += 1
        bb_pos = features.get("bb_position")
        if bb_pos is not None and (bb_pos > 0.95 or bb_pos < 0.05):
            stretched += 1
        if stretched:
            score += 0.3 if stretched == 1 else 0.4

        # EMA crossover EVENT (sign change this candle, not mere separation)
        if features.get("ema_cross_signal"):
            score += 0.25

        # Volume spike — current closed candle vs the average of the PRIOR 20
        # (including itself in the average dampens the very spike we look for)
        if len(candles) >= 21:
            avg_vol = sum(c["volume"] for c in candles[-21:-1]) / 20
            if avg_vol > 0 and candles[-1]["volume"] > avg_vol * config.VOLUME_SPIKE_MULT:
                score += 0.25

        # Consecutive directional candles (momentum)
        if len(candles) >= 4:
            closes = [c["close"] for c in candles[-4:]]
            if all(closes[i] < closes[i + 1] for i in range(3)):
                score += 0.15
            elif all(closes[i] > closes[i + 1] for i in range(3)):
                score += 0.15

        return min(score, 1.0)

    async def _llm_analyze(
        self,
        symbol: str,
        timeframe: str,
        candles: list[dict],
        features: dict,
        live_price: float,
    ) -> dict | None:
        # Render chart with indicator overlays
        chart_candles = candles[-config.CHART_CANDLES:]
        hist_key = f"{symbol}:{timeframe}"
        feat_list = list(self._features_history.get(hist_key, []))
        if len(feat_list) > len(chart_candles):
            feat_list = feat_list[-len(chart_candles):]
        elif len(feat_list) < len(chart_candles):
            feat_list = None

        # Run chart rendering, Brave research, and derivatives fetch in parallel
        research_text = ""
        deriv_text = ""
        io_tasks = []

        if self.researcher:
            io_tasks.append(("research", asyncio.create_task(
                self.researcher.research_asset(symbol)
            )))
        if self.derivatives:
            io_tasks.append(("derivatives", asyncio.create_task(
                self.derivatives.get(symbol, live_price)
            )))

        # Matplotlib rendering takes hundreds of ms — keep it off the event
        # loop so the websocket streams don't stall
        chart_b64 = await asyncio.to_thread(
            self.charts.render_with_indicators,
            chart_candles, feat_list, f"{symbol} {timeframe}",
        )

        # Collect I/O results
        for name, task in io_tasks:
            try:
                result = await task
                if name == "research":
                    research_text = result
                elif name == "derivatives":
                    deriv_text = self.derivatives.format_for_llm(result)
            except Exception as e:
                print(f"[{name.upper()}] Error for {symbol}: {e}")

        # Build structured text context
        context_candles = candles[-config.CONTEXT_CANDLES:]
        candle_text = "| Time | Open | High | Low | Close | Volume |\n"
        candle_text += "|------|------|------|-----|-------|--------|\n"
        for c in context_candles:
            ts = time.strftime("%m-%d %H:%M", time.gmtime(c["timestamp"] / 1000))
            candle_text += (
                f"| {ts} | {c['open']:.2f} | {c['high']:.2f} | "
                f"{c['low']:.2f} | {c['close']:.2f} | {c['volume']:.0f} |\n"
            )

        def fmt(key, spec=".2f"):
            val = features.get(key)
            return f"{val:{spec}}" if val is not None else "N/A"

        rsi_str = fmt("rsi", ".1f")
        bb_pos_str = fmt("bb_position")
        ema_fast_str = fmt("ema_fast")
        ema_slow_str = fmt("ema_slow")
        atr_str = fmt("atr")
        cross_str = features.get("ema_cross_signal") or "none"

        news_text = self.news.format_for_llm(symbol, n=8) if self.news else ""

        text_context = f"""## {symbol} {timeframe} — Live Analysis

**Live Price:** {live_price:.2f}
**Last Closed Candle:** {features['close']:.2f} (indicators below are computed on closed candles)
**RSI(14):** {rsi_str}
**EMA(9):** {ema_fast_str}
**EMA(21):** {ema_slow_str}
**EMA Crossover This Candle:** {cross_str}
**BB Position:** {bb_pos_str} (0=lower band, 1=upper band)
**ATR(14):** {atr_str}
**Trend:** {features.get('trend', 'N/A')}
**Market Regime:** {self.regime.get(symbol, timeframe)}

### Recent Candles
{candle_text}

### Higher-Timeframe Bias
{self._higher_tf_bias(symbol, timeframe)}

### Prior Analyses
{self.memory.get_recent_summary(symbol, n=3)}

### Trend Bias
{self.memory.get_bias(symbol)}

### Learned Patterns
{self.memory.get_reflections(symbol, n=3)}

### News (RSS/CryptoPanic)
{news_text or "No news feed data."}

### Derivatives (Funding Rate / Open Interest)
{deriv_text or "No derivatives data."}

### Live Research (Brave Search)
{research_text or "No research data."}

### Signal Track Record
{self.outcomes.get_stats_summary() if self.outcomes else "No outcome tracking."}

### Portfolio State
{self.portfolio.format_for_llm() if self.portfolio else "No portfolio tracking."}
"""

        return await self.llm.analyze(chart_b64, text_context)

    def _higher_tf_bias(self, symbol: str, current_tf: str) -> str:
        """Summarize the latest features of higher timeframes so a 1m signal
        is read in the context of the 1h/4h trend (multi-timeframe check)."""
        lines = []
        for tf in config.BIAS_TIMEFRAMES:
            if tf == current_tf:
                continue
            hist = self._features_history.get(f"{symbol}:{tf}")
            if not hist:
                continue
            f = hist[-1]
            rsi = f.get("rsi")
            rsi_str = f"{rsi:.0f}" if rsi is not None else "N/A"
            regime = self.regime.get(symbol, tf)
            lines.append(
                f"- {tf}: trend {f.get('trend', 'N/A')}, RSI {rsi_str}, "
                f"regime {regime}"
            )
        return "\n".join(lines) or "No higher-timeframe data."

    async def _emit_signal(self, symbol: str, timeframe: str, analysis: dict):
        for cb in self.signal_callbacks:
            try:
                await cb(symbol, timeframe, analysis)
            except Exception as e:
                print(f"[SIGNAL] Callback error: {e}")
