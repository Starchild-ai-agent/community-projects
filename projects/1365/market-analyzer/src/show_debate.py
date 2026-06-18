#!/usr/bin/env python3
"""Print the full raw LLM debate text for inspection."""

import asyncio, os, sys, time, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

def make_candles(n, base, trend, vol=0.008, seed=42):
    rng = random.Random(seed)
    candles, price = [], base
    for i in range(n):
        drift = trend + rng.gauss(0, abs(trend)*0.5 + vol*price*0.1)
        price += drift
        body = abs(rng.gauss(0, price*vol*0.5))
        wu = abs(rng.gauss(0, price*vol*0.3))
        wd = abs(rng.gauss(0, price*vol*0.3))
        o, c = (price-body, price) if drift >= 0 else (price, price-body)
        candles.append({"timestamp": 1700000000000+i*3600000,
            "open": round(o,2), "high": round(max(o,c)+wu,2),
            "low": round(min(o,c)-wd,2), "close": round(c,2),
            "volume": round(max(50, rng.gauss(800,300)),2)})
    return candles

async def main():
    from importlib import import_module
    cfg = import_module("market-analyzer.config")
    llm_mod = import_module("market-analyzer.llm_client")
    features_mod = import_module("market-analyzer.features")
    charts_mod = import_module("market-analyzer.charts")

    candles = make_candles(60, 100000, 60, seed=77)
    engine = features_mod.FeatureEngine()
    feat_list = []
    for c in candles:
        feat = engine.update("BTC/USDT", "1h", c)
        feat_list.append(feat)

    chart_b64 = charts_mod.ChartRenderer().render_with_indicators(
        candles[-60:], feat_list[-60:], title="BTC/USDT 1h")

    rsi = f"{feat['rsi']:.1f}" if feat.get("rsi") else "N/A"
    bb = f"{feat['bb_position']:.2f}" if feat.get("bb_position") else "N/A"
    ef = f"{feat['ema_fast']:.2f}" if feat.get("ema_fast") else "N/A"
    es = f"{feat['ema_slow']:.2f}" if feat.get("ema_slow") else "N/A"
    atr = f"{feat['atr']:.2f}" if feat.get("atr") else "N/A"

    rows = ""
    for c in candles[-20:]:
        ts = time.strftime("%m-%d %H:%M", time.gmtime(c["timestamp"]/1000))
        rows += f"| {ts} | {c['open']:.2f} | {c['high']:.2f} | {c['low']:.2f} | {c['close']:.2f} | {c['volume']:.0f} |\n"

    text = f"""## BTC/USDT 1h — Live Analysis

**Current Price:** {feat['close']:.2f}
**RSI(14):** {rsi}
**EMA(9):** {ef}
**EMA(21):** {es}
**BB Position:** {bb} (0=lower band, 1=upper band)
**ATR(14):** {atr}
**Trend:** {feat.get('trend','N/A')}

### Recent Candles
| Time | Open | High | Low | Close | Volume |
|------|------|------|-----|-------|--------|
{rows}
### Prior Analyses
- 14:00 1h: BUY (strength: 65, trend: bullish) — Breakout above resistance with volume
- 13:00 1h: HOLD (strength: 40, trend: neutral) — Consolidating near EMA9

### Learned Patterns
- BTC/USDT BUY at 99500 (strength 65) — CORRECT. Returns: 1h=0.8%, 4h=1.2%. Dip-buying in uptrend works.
- BTC/USDT BUY at 101000 (strength 72) — WRONG. Returns: 1h=-0.5%, 4h=-1.8%. Overbought signal was ignored.

### News (RSS/CryptoPanic)
- Bitcoin ETF sees $500M inflows [positive] (coindesk.com, 2h ago)
- Fed signals potential rate pause [positive] (reuters.com, 4h ago)
- Whale moves 5000 BTC to exchange [negative] (cryptopanic.com, 1h ago)

### Derivatives (Funding Rate / Open Interest)
**Funding Rate:** 0.0120% per 8h (moderately_long)
  → Longs paying shorts — mild bullish positioning
**Open Interest:** $18,500,000,000

### Portfolio State
**Balance:** $10,000.00 | **Equity:** $10,250.00
**Realized P&L:** +$250.00 | **Drawdown:** 0.0%
**Trades:** 4 | **Win Rate:** 3/4 (75%)

**Open Positions:**
- LONG BTC/USDT: entry $99,500.00, size $750, P&L +2.51%

**Exposure:** $750 / $3,000 max
"""

    payload = {
        "model": cfg.LLM_MODEL,
        "max_tokens": cfg.LLM_MAX_TOKENS,
        "messages": [
            {"role": "system", "content": llm_mod.SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{chart_b64}"}},
                {"type": "text", "text": text},
            ]},
        ],
    }

    print("Calling LLM...\n")
    t0 = time.time()
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            f"{cfg.OPENROUTER_BASE_URL}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {cfg.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://starchild.ai",
                "X-Title": "Market Analyzer",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    raw = data["choices"][0]["message"]["content"]
    tokens = data.get("usage", {}).get("total_tokens", 0)
    model = data.get("model", cfg.LLM_MODEL)
    elapsed = time.time() - t0

    print(f"Model: {model} | {tokens} tokens | {elapsed:.1f}s\n")
    print("=" * 70)
    print(raw)
    print("=" * 70)

asyncio.run(main())
