# Crypto Market Board

Live top-10 crypto market snapshot (CoinGecko, 2026-09-29): prices, 24h/7d moves, 24h range bars, volume, market cap and ATH context.

## What

- Summary strip: top-10 total market cap, best/worst 24h performer, breadth
- 10 coin cards with price, 24h%/7d% pills, 24h high/low bar, volume, ATH delta
- Market-cap sorted table

## Required env

None. Fully static snapshot, no API keys. Empty `.env.example` included for layout consistency.

## How to start

Open `src/index.html` directly in any browser. Or serve: `python3 -m http.server 8915 --directory src`.

## Outputs

- `src/index.html`: self-contained dashboard (no CDN, no fetch)
- `output/market-board-data.json`: source snapshot

## Troubleshooting

- 7d% shows "—": CoinGecko snapshot had null 7d values that day; file renders nulls as "—" by design.
- If styles look off, ensure you open the single file directly (no build step needed).
