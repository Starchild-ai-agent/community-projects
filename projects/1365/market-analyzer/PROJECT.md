# Market Analyzer

A live crypto market analysis agent that streams exchange data 24/7 and uses a 3-tier architecture to fire LLM analysis only when something interesting happens — then learns from its own performance over time.

## What

- **Tier 1:** Fast rule-based screener (RSI, volume spikes, EMA crossovers) — runs on every candle close, <1ms
- **Regime filter:** Classifies market state (trending/ranging/volatile) and adjusts Tier 1 sensitivity
- **Tier 2:** Multimodal LLM analysis (chart image + indicators + news + research) via Claude Sonnet 4.6 — fires only ~5-20×/day
- **Tier 3:** Signal emission with full risk management gate (exposure limits, correlation checks, drawdown guard)
- **Self-tuner:** Tracks win/loss outcomes and auto-adjusts thresholds hourly — no human intervention needed

## Required env

| Variable | Description |
|---|---|
| `MA_SYMBOLS` | Comma-separated symbols, e.g. `BTC/USDT,ETH/USDT,SOL/USDT` |
| `MA_EXCHANGE` | Exchange to stream from (default: `binance`) |
| `OPENROUTER_API_KEY` | OpenRouter API key (or use SC-Proxy — no key needed on Starchild) |
| `COINGLASS_API_KEY` | Optional — enables derivatives data (funding/OI/liquidations) |
| `BRAVE_API_KEY` | Optional — enables live web research alongside RSS news |

## How to start

```bash
pip install -r src/requirements.txt
python3 -m market-analyzer          # starts streaming + analysis loop
```

Or run the dashboard in parallel:
```bash
python3 -m market-analyzer.run_dashboard
```

## Outputs

- Structured JSON signals to stdout: `{"action": "BUY", "symbol": "BTC/USDT", "conviction": 72, ...}`
- `outcomes.json` — win/loss tracking per signal
- `memory.json` — the LLM's own reflections injected into future calls
- Dashboard at `http://localhost:8080` for live monitoring

## Troubleshooting

- **401 from OpenRouter:** Set `OPENROUTER_API_KEY`, or run on Starchild (SC-Proxy injects auth automatically via `STARCHILD_API_PROXY_*` env)
- **No signals firing:** Lower `MA_SCREEN_THRESHOLD` (default 0.6) or add more volatile symbols
- **LLM costs too high:** Raise `MA_SCREEN_THRESHOLD` to 0.8 — Tier 1 will filter more aggressively
- **Want a different model:** Set `MA_LLM_MODEL=anthropic/claude-haiku-4.5` for cheaper/faster calls
