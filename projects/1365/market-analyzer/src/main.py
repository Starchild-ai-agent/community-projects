#!/usr/bin/env python3
"""
Live Market Analysis Agent

Usage:
    # Default: BTC/USDT, ETH/USDT, SOL/USDT on Binance
    python -m market-analyzer

    # Custom symbols and exchange
    MA_EXCHANGE=bybit MA_SYMBOLS=BTC/USDT,WOO/USDT python -m market-analyzer

    # Dashboard on custom port
    MA_DASHBOARD_PORT=3000 python -m market-analyzer
"""

import asyncio
import json
import os
import time
import signal as sig
from dataclasses import asdict
from pathlib import Path

import uvicorn

from . import config
from .stream import MarketStream
from .features import FeatureEngine
from .charts import ChartRenderer
from .memory import AnalysisMemory
from .llm_client import LLMClient
from .news import NewsFeed
from .research import BraveResearcher
from .outcomes import OutcomeTracker
from .portfolio import Portfolio
from .derivatives import DerivativesData
from .self_tune import SelfTuner
from .analyzer import AnalysisLoop
from .dashboard import Dashboard


# Global dashboard instance for signal callbacks
dashboard = Dashboard()


async def on_signal(symbol: str, timeframe: str, analysis: dict):
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    action = analysis.get("action", "?")
    strength = analysis.get("signal_strength", 0)
    trend = analysis.get("trend", "?")
    pattern = analysis.get("pattern", "")
    reasoning = analysis.get("reasoning", "")
    risk = analysis.get("risk", "?")
    catalyst = analysis.get("catalyst", "")
    news_impact = analysis.get("news_impact", "none")
    regime = analysis.get("regime", "?")
    bull = analysis.get("bull_conviction", "?")
    bear = analysis.get("bear_conviction", "?")
    invalidation = analysis.get("invalidation", "")
    levels = analysis.get("key_levels", {})
    support = levels.get("support", "?")
    resistance = levels.get("resistance", "?")

    print(f"\n{'='*60}")
    print(f"[SIGNAL] {ts}")
    print(f"  {symbol} {timeframe}: {action}")
    print(f"  Strength: {strength}/100 | Trend: {trend} | Risk: {risk}")
    print(f"  Bull: {bull} vs Bear: {bear} | Regime: {regime}")
    print(f"  Pattern: {pattern}")
    print(f"  Support: {support} | Resistance: {resistance}")
    if invalidation:
        print(f"  Invalidation: {invalidation}")
    print(f"  News: {news_impact}", end="")
    if catalyst:
        print(f" — {catalyst}")
    else:
        print()
    print(f"  Reasoning: {reasoning}")
    print(f"{'='*60}\n")

    # Push to dashboard
    await dashboard.push_signal(symbol, timeframe, analysis)


async def run():
    print(f"[INIT] Exchange: {config.EXCHANGE}")
    print(f"[INIT] Symbols: {config.SYMBOLS}")
    print(f"[INIT] Timeframes: {config.TIMEFRAMES}")
    print(f"[INIT] Screen threshold: {config.SCREEN_THRESHOLD}")
    print(f"[INIT] LLM: {config.LLM_MODEL}")
    print(f"[INIT] LLM call mode: {config.LLM_CALL_MODE}")
    print(f"[INIT] Analysis cooldown: {config.ANALYSIS_COOLDOWN}s")
    print()

    stream = MarketStream()
    features = FeatureEngine()
    charts = ChartRenderer()
    llm = LLMClient()
    persist = "./market-analyzer-data"
    memory = AnalysisMemory(persist_dir=persist)
    news = NewsFeed(poll_interval=300)
    researcher = BraveResearcher() if config.BRAVE_API_KEY else None
    outcomes = OutcomeTracker(memory, persist_dir=persist)
    portfolio = Portfolio(
        initial_balance=10000.0,
        max_position_pct=0.10,
        max_total_exposure_pct=0.30,
        max_drawdown_pct=0.15,
        max_hold_seconds=config.MAX_HOLD_HOURS * 3600,
        persist_dir=persist,
    )
    derivatives = DerivativesData()
    self_tuner = SelfTuner(outcomes, memory, review_interval=3600, persist_dir=persist)

    print(f"[INIT] News: RSS + CryptoPanic")
    print(f"[INIT] Derivatives provider: {config.DERIV_PROVIDER}")
    print(f"[INIT] Brave Research: {'enabled' if researcher else 'disabled (set BRAVE_API_KEY)'}")
    print(
        f"[INIT] Twitter enrichment: "
        f"{'enabled' if config.ENABLE_TWITTER_NEWS else 'disabled'}"
    )
    print(f"[INIT] Outcome tracking: enabled ({outcomes.stats['total_signals']} prior signals)")
    if outcomes.stats["total_signals"] > 0:
        print(f"[INIT] Track record: {outcomes.get_stats_summary()}")
    print(f"[INIT] Portfolio: ${portfolio.state.balance:.0f} balance, "
          f"{len(portfolio.state.positions)} positions")
    print(f"[INIT] Self-tuner: enabled (reviews every {self_tuner.review_interval}s)")

    dash_port = int(os.getenv("MA_DASHBOARD_PORT", "3333"))
    dash_host = config.DASHBOARD_HOST
    print(f"[INIT] Dashboard: http://{dash_host}:{dash_port}")
    print()

    analyzer = AnalysisLoop(
        features, charts, llm, memory,
        news=news, researcher=researcher,
        outcomes=outcomes, portfolio=portfolio,
        derivatives=derivatives, self_tuner=self_tuner,
    )
    analyzer.signal_callbacks.append(on_signal)
    analyzer.dashboard = dashboard

    # Feed resolved outcomes and self-tune adjustments to the dashboard panels
    outcomes.on_outcome = lambda r: asyncio.create_task(
        dashboard.push_outcome(asdict(r))
    )
    self_tuner.on_adjustments = lambda adjs: asyncio.create_task(
        dashboard.push_self_tune(adjs)
    )

    # Seed the panels with recent history from disk so a fresh page isn't empty
    recent_outcomes = []
    results_path = Path(persist) / "results.jsonl"
    if results_path.exists():
        seen_ids = set()
        for line in results_path.read_text().strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Old versions re-appended results; dedupe by signal_id
            sid = r.get("signal_id")
            if sid in seen_ids:
                continue
            seen_ids.add(sid)
            recent_outcomes.append(r)
    dashboard.seed(
        outcomes=recent_outcomes[-20:],
        adjustments=self_tuner.adjustments_log[-15:],
    )

    stream.on_candle(analyzer.on_candle)

    # Pre-fill buffers with historical data, then warm up features engine
    await stream._prefill()
    for symbol in config.SYMBOLS:
        for tf in config.TIMEFRAMES:
            candles = list(stream.buffers[symbol].timeframes[tf])
            if candles:
                analyzer.warmup(symbol, tf, candles)

    # Graceful shutdown
    loop = asyncio.get_event_loop()
    stop = asyncio.Event()

    def shutdown():
        print("\n[SHUTDOWN] Closing connections...")
        stop.set()

    for s in (sig.SIGINT, sig.SIGTERM):
        loop.add_signal_handler(s, shutdown)

    # Start dashboard web server
    app = dashboard.get_app()
    # Localhost by default — the dashboard is unauthenticated. Set
    # MA_DASHBOARD_HOST=0.0.0.0 explicitly to expose it on the network.
    dash_config = uvicorn.Config(app, host=dash_host, port=dash_port, log_level="warning")
    dash_server = uvicorn.Server(dash_config)
    dash_task = asyncio.create_task(dash_server.serve())

    # Fetch news once before starting, then poll in background
    print("[INIT] Fetching initial news...")
    await news._fetch_all()
    print(f"[INIT] News loaded: {len(news._cache)} items")
    news_task = asyncio.create_task(news.start())

    # Periodic state push to dashboard (every 10s)
    async def push_state_loop():
        while not stop.is_set():
            state = {
                "portfolio": {
                    "equity": portfolio.state.equity,
                    "balance": portfolio.state.balance,
                    "realized_pnl": portfolio.state.realized_pnl,
                    "drawdown": portfolio.state.drawdown,
                    "trade_count": portfolio.state.trade_count,
                    "win_count": portfolio.state.win_count,
                    "positions": {
                        k: {
                            "symbol": v.symbol,
                            "side": v.side,
                            "entry_price": v.entry_price,
                            "size": v.size,
                            "unrealized_pnl_pct": v.unrealized_pnl_pct,
                        }
                        for k, v in portfolio.state.positions.items()
                    },
                },
                "outcomes": outcomes.stats,
            }
            await dashboard.push_state(state)
            await asyncio.sleep(10)

    state_task = asyncio.create_task(push_state_loop())

    # Run stream until stop signal
    stream_task = asyncio.create_task(stream.start())
    await stop.wait()

    stream_task.cancel()
    news_task.cancel()
    state_task.cancel()
    dash_server.should_exit = True
    try:
        await asyncio.gather(stream_task, news_task, state_task, dash_task,
                             return_exceptions=True)
    except asyncio.CancelledError:
        pass

    await stream.close()
    await news.close()
    await derivatives.close()
    if researcher:
        await researcher.close()
    print("[SHUTDOWN] Done.")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
