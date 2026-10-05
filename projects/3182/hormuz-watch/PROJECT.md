# Hormuz Watch

Global oil-shock and chokepoint monitor. Single-page dark dashboard tracking the US–Iran war's energy fallout: live crude benchmarks (TwelveData BNO/UCO proxies), chokepoint status board, G7 100M-barrel reserve release tracker, escalation ladder, and a dated event timeline. All news rows sourced and dated.

## Data
- Live: TwelveData quote API (BNO Brent proxy, UCO WTI proxy)
- Reported: Brent/WTI front, US diesel $6.37/gal, OPEC+ decision — CNBC / Economic Times / Al Jazeera (Oct 4–5, 2026)

## Run
Static site — `src/index.html`, no build step, no env vars.

## What
Hormuz Watch is a single-page oil-shock monitor: chokepoint status board, live crude proxy quotes (BNO/UCO), G7 100M-barrel reserve release tracker, escalation ladder and dated event timeline. All news rows sourced and dated.

## Required env
None. (Optional: TWELVEDATA_API_KEY — auto-injected by the platform at runtime.)

## How to start
Static site — open `src/index.html`, or serve the directory:
```
python3 -m http.server 8917 --directory src
```

## Outputs / Behavior
Dark dashboard rendering: crisis alert banner, 4 live-price cards, chokepoint table, G7 release tracker, escalation timeline, escalation ladder, market read. No build step.

## Troubleshooting
- Prices stale → page embeds Oct 5, 2026 snapshot; refresh quotes via TwelveData `quote` endpoint for BNO/UCO.
- Blank page → ensure served over HTTP (not file://) so relative assets load.
