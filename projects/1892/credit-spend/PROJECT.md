# Credit Spend

A forkable dashboard that shows you exactly where your Starchild credits go: by day, by model, by task type, by agent, and per-charge.

Pulls live from the internal Credit API at `http://starchild-credit-api.internal:8080`, which auto-identifies your container. **Your data never leaves your machine** — no auth, no external network, no saved credentials.

## What it shows

- **Current balance** + lifetime used / recharged
- **Daily spend** (7 / 14 / 30 / 60 / 90 day windows)
- **By task type** — chat (you typing), schedule (cron jobs), subagent (spawned tasks), classify/title/compact (system overhead)
- **By model family** — Claude Opus vs Sonnet vs Haiku vs GPT Codex vs Gemini vs DeepSeek vs image generation vs market-data APIs
- **By agent** — main agent vs sub-agents vs system
- **Stacked daily breakdown by model** — see which model dominated each day
- **Last 50 individual charges** with exact cost per call

## Required env

None. The dashboard talks to the Starchild internal Credit API, which is reachable from every user container without auth.

## How to start

1. Install dependencies:
   ```bash
   pip install fastapi uvicorn httpx
   ```
2. Run the server:
   ```bash
   python src/server.py
   ```
3. Open the dashboard via the Starchild preview tool, pointing at `port=7821` and `dir=src/`.

After forking, just run it — there is nothing to configure.

## Outputs

This is a read-only viewer. It does not write any files or modify your account in any way.

## Troubleshooting

- **"Failed to load: ... 502/503"** — the internal Credit API is temporarily unreachable. Wait a few seconds and hit Refresh.
- **Numbers look low compared to my Stripe top-ups** — the dashboard shows usage charges. Top-ups appear in `lifetime recharged`, not in daily/breakdown views.
- **Breakdown is `truncated: true`** — the per-charge aggregator stops after 4000 charges to keep the UI snappy. For longer windows, raise `max_pages` in `src/server.py`'s `/api/breakdown` route.
