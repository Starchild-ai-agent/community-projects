#!/usr/bin/env python3
"""
Run dashboard with live Binance data (free, no API key).
Usage: python market-analyzer/run_dashboard.py
"""

import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
import ccxt.pro as ccxtpro
from importlib.util import spec_from_file_location, module_from_spec

_dir = os.path.dirname(os.path.abspath(__file__))
spec = spec_from_file_location("_dashboard", os.path.join(_dir, "dashboard.py"))
mod = module_from_spec(spec)
sys.modules["_dashboard"] = mod
spec.loader.exec_module(mod)
Dashboard = mod.Dashboard

dashboard = Dashboard()

SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

# Track state
prices = {}
prev_prices = {}
candle_data = {}  # symbol -> list of recent closes
volumes = {}  # symbol -> list of recent volumes


async def stream_prices():
    exchange = ccxtpro.binance({"enableRateLimit": True})

    print("[STREAM] Connecting to Binance free WebSocket...")

    async def watch(symbol):
        last_ts = 0
        while True:
            try:
                ohlcv = await exchange.watch_ohlcv(symbol, "1m")
                if not ohlcv:
                    continue

                latest = ohlcv[-1]
                ts, o, h, l, c, v = latest

                # Store price
                prev_prices[symbol] = prices.get(symbol, c)
                prices[symbol] = c

                # Track recent closes and volumes for scoring
                if symbol not in candle_data:
                    candle_data[symbol] = []
                    volumes[symbol] = []

                # New candle closed (timestamp changed)
                if ts != last_ts and last_ts != 0:
                    candle_data[symbol].append(c)
                    volumes[symbol].append(v)
                    # Keep last 30
                    candle_data[symbol] = candle_data[symbol][-30:]
                    volumes[symbol] = volumes[symbol][-30:]

                    # Calculate a real score
                    score, reasons = calc_score(symbol, c, v)
                    regime = detect_regime(symbol)

                    # Only log if score > 0.1 (filter noise)
                    if score >= 0.1:
                        # Only say ESCALATING if above threshold
                        if score >= 0.6:
                            await dashboard.push_tier1(symbol, "1m", score, regime)
                        else:
                            # Just show as a price update in the log
                            pass

                    # Always push price update to log (throttled)
                    change = ((c - prev_prices[symbol]) / prev_prices[symbol] * 100) if prev_prices[symbol] else 0
                    change_str = f"+{change:.3f}%" if change >= 0 else f"{change:.3f}%"

                    # Push as a system message showing live prices
                    from _dashboard import Dashboard as D
                    msg = (
                        f"[PRICE] {symbol} ${c:,.2f} ({change_str}) "
                        f"vol:{v:,.0f}"
                    )
                    if reasons:
                        msg += f"  [{', '.join(reasons)}]"

                    await dashboard.broadcast("tier1_info", {
                        "symbol": symbol,
                        "price": c,
                        "change": round(change, 4),
                        "volume": v,
                        "score": round(score, 2),
                        "regime": regime,
                        "reasons": reasons,
                    })

                last_ts = ts

            except Exception as e:
                print(f"[STREAM] {symbol}: {e}")
                await asyncio.sleep(5)

    tasks = [watch(s) for s in SYMBOLS]
    await asyncio.gather(*tasks)


def calc_score(symbol, close, volume):
    """Simple real scoring based on actual market data."""
    score = 0.0
    reasons = []

    closes = candle_data.get(symbol, [])
    vols = volumes.get(symbol, [])

    if len(closes) < 5:
        return 0.0, []

    # Volume spike (2x average)
    if len(vols) >= 10:
        avg_vol = sum(vols[-10:]) / 10
        if avg_vol > 0 and volume > avg_vol * 2:
            score += 0.25
            reasons.append("VOL SPIKE")

    # 3+ consecutive direction
    if len(closes) >= 4:
        last4 = closes[-4:]
        if all(last4[i] < last4[i+1] for i in range(3)):
            score += 0.2
            reasons.append("MOMENTUM UP")
        elif all(last4[i] > last4[i+1] for i in range(3)):
            score += 0.2
            reasons.append("MOMENTUM DOWN")

    # Big candle move (> 0.3% in 1 candle)
    if len(closes) >= 2:
        move = abs(closes[-1] - closes[-2]) / closes[-2] * 100
        if move > 0.3:
            score += 0.2
            reasons.append(f"BIG MOVE {move:.2f}%")

    # Price at extremes of recent range
    if len(closes) >= 20:
        hi = max(closes[-20:])
        lo = min(closes[-20:])
        rng = hi - lo
        if rng > 0:
            pos = (close - lo) / rng
            if pos > 0.95:
                score += 0.15
                reasons.append("AT HIGH")
            elif pos < 0.05:
                score += 0.15
                reasons.append("AT LOW")

    return min(score, 1.0), reasons


def detect_regime(symbol):
    closes = candle_data.get(symbol, [])
    if len(closes) < 15:
        return "unknown"

    recent = closes[-15:]
    first_half = sum(recent[:7]) / 7
    second_half = sum(recent[7:]) / len(recent[7:])
    change = (second_half - first_half) / first_half * 100

    if change > 0.3:
        return "trending_up"
    elif change < -0.3:
        return "trending_down"

    # Range check
    hi = max(recent)
    lo = min(recent)
    spread = (hi - lo) / lo * 100
    if spread < 0.5:
        return "low_vol"
    elif spread > 2:
        return "high_vol"

    return "range"


async def push_state_loop():
    while True:
        price_lines = {}
        for s in SYMBOLS:
            if s in prices:
                prev = prev_prices.get(s, prices[s])
                chg = ((prices[s] - prev) / prev * 100) if prev else 0
                price_lines[s] = {"price": prices[s], "change": round(chg, 4)}

        await dashboard.push_state({
            "portfolio": {
                "equity": 10000,
                "balance": 10000,
                "realized_pnl": 0,
                "drawdown": 0,
                "trade_count": 0,
                "win_count": 0,
                "positions": {},
            },
            "outcomes": {
                "total_signals": 0,
                "correct": 0,
                "incorrect": 0,
                "win_rate": 0,
                "avg_return_1h": 0,
                "avg_return_4h": 0,
            },
            "prices": price_lines,
        })
        await asyncio.sleep(10)


async def main():
    port = 3333
    host = os.getenv("MA_DASHBOARD_HOST", "127.0.0.1")
    app = dashboard.get_app()
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)

    print(f"\n  STARCHILD MARKET TERMINAL")
    print(f"  http://localhost:{port}")
    print(f"  Live data from Binance (free WebSocket)\n")

    await asyncio.gather(
        server.serve(),
        stream_prices(),
        push_state_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
