# WhaleFlow Terminal

## What

WhaleFlow Terminal is a multi-asset market intelligence dashboard that monitors:

- Crypto order-flow proxies (funding, open interest change, liquidations)
- Hyperliquid whale position activity
- TradFi tape (indices, FX, commodities)
- Market-moving headlines with sources and publication times
- Composite risk regime scoring (Risk-On / Mixed / Risk-Off)

This project provides a practical, always-accessible alternative to proprietary institutional terminals by combining high-signal public/proxy datasets in a single interface.

## Required env

In Starchild hosted mode, proxy credentials are injected automatically.

For external/local usage, set:

- `COINGLASS_API_KEY`
- `TWELVEDATA_API_KEY`

Example file is provided at `.env.example`.

## How to start

From the project directory, run:

```bash
uvicorn app:app --host 0.0.0.0 --port 8787
```

Then open your preview URL.

## Outputs / Behavior

- `/` serves the dashboard UI
- `/api/snapshot` returns JSON with:
  - `crypto` (flow metrics + whale bias)
  - `tradfi` (quotes across indices/FX/commodities)
  - `news` (source-tagged headlines)
  - `regime` (score + label)
- Frontend auto-refresh supports 30s/60s intervals
- News cards include source and publication time

## Troubleshooting

- If dashboard shows empty data, verify the API keys/environment and retry refresh.
- If only some panels are blank, upstream providers may be temporarily rate-limited.
- If preview is down, restart the service and confirm it is running before publishing.
- Bloomberg proprietary full order-book flow is not public; this project uses public/proxy whale/order-flow signals.
