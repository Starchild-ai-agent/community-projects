# Live Market Analysis Agent — TLDR

**What it is:** A system that streams live crypto market data 24/7 and uses an AI agent in a continuous loop to analyze chart movements, news, and market conditions — then learns from its own performance over time.

**The problem it solves:** Human traders can't watch every chart on every timeframe simultaneously. LLMs are too slow and expensive to call on every candle. We need a tiered system that's always watching but only thinks deeply when something interesting happens.

## How It Works

### 3-Tier Architecture:

| Tier | What | Speed | Frequency |
|------|------|-------|-----------|
| **Tier 1** | Fast rule-based screen (RSI, volume spikes, EMA crossovers) | <1ms | Every candle close |
| **Regime Filter** | Classifies market (trending/ranging/volatile) and adjusts Tier 1 behavior | <1ms | Every candle close |
| **Tier 2** | Multimodal LLM analysis — sends chart image + indicators + news + research to Claude via OpenRouter | 2-10s | Only when Tier 1 flags something (~5-20x/day) |
| **Tier 3** | Signal emission with risk management gate | Instant | Only on BUY/SELL decisions |

Tier 1 filters out ~90% of candles as uninteresting. The LLM only fires when it matters.

### What the LLM Sees (on each Tier 2 trigger)

- Rendered candlestick chart image with indicator overlays (EMA, Bollinger Bands, RSI)
- Structured price data (last 20 candles as a table)
- Technical indicators (RSI, EMA, BB position, ATR)
- Market regime classification (trending up/down, range, high/low volatility)
- Funding rates & open interest (crowd positioning data)
- News headlines from CoinDesk, CoinTelegraph, TheBlock with sentiment tags
- Live Brave Search results (3 parallel queries: asset news, analysis context, macro sentiment)
- Its own prior analyses and track record
- Current portfolio state (open positions, exposure, drawdown)

### The LLM's Process (forced structured debate)

The AI doesn't just output a signal. It must:
1. Describe what it sees on the chart
2. Read the indicators
3. Digest the news
4. **Argue the bull case** (as if it must go long)
5. **Argue the bear case** (as if it must go short)
6. Check the market regime
7. Synthesize a final decision with conviction scores for both sides

If bull and bear are close → HOLD. No forced calls.

### Risk Management

Before any signal goes live, it passes through a risk gate:
- Already in this position? → Blocked
- Total exposure at max? → Blocked
- Too many correlated positions (BTC + ETH = same bet)? → Blocked
- In drawdown beyond limit? → Blocked
- Position size scaled by signal strength (weak signal = small bet)

Open positions have a full exit lifecycle:
- **Stop**: the LLM's invalidation level, parsed to a price
- **Target**: the opposite key level (resistance for longs, support for shorts)
- **Max hold**: force-closed after 24h so exposure recycles
- Flipping direction realizes the old position's P&L first

The LLM itself only trades when its debate clears two bars: a 16+ point
conviction gap AND the winning side at ≥50 conviction. A lopsided-but-weak
debate (bull 35 vs bear 10) is a HOLD, not a forced trade.

### The Self-Improvement Loop (the key innovation)

The system recursively improves itself without human intervention:

```
Signals emitted → Outcomes tracked (checkpoints scaled to the signal's
        timeframe: a 1m scalp is judged at 15m/1h, a 4h swing at 24h;
        moves inside the fee threshold count as neither win nor loss)
    → Win/loss scored → Reflections generated
    → Reflections injected into future LLM calls ("last time you called BUY here, it was wrong")
    → Self-tuner reviews hourly:
        - Win rate too low? → Raise screening threshold (be more selective)
        - Win rate high? → Lower threshold (catch more setups)
        - Recent losing streak? → Increase cooldown (slow down)
        - Model overconfident? → Inject calibration warning
    → Better signals → Better outcomes → Better reflections → ...
```

