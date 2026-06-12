# QuoteSim — quote any asset, with a trust score

A market-maker simulator that is honest about its own error bars.

## What

Most MM backtests lie: OHLC touch-fill models overcount fills **8–25×** vs
reality. QuoteSim leads with that fact instead of hiding it:

- **Simulate** a two-sided laddered quoting strategy (levels, spread, band,
  inventory caps, close-skew) on any oracle-backed asset:
  - any Hyperliquid perp (oracle = data venue, by construction)
  - curated Pyth RWA feeds (US equities, metals, FX majors)
  - any exchange+pair via the optional CoinGlass path
- **Calibrate** against ground truth: every estimate is scaled through a real
  production NATGAS MM bot's measured fills-per-day / $-per-day, not raw model
  output.
- **Trust score (0–100)** on every result. Until a strategy is validated
  against real tape, the dashboard labels dollar estimates
  *"Fast preview — risk shape is real; validate for exact $"* — and means it.
- **Phase 2 paper-live**: shadow-quote real Orderly markets in real time with
  zero keys and zero custody (`paperlive_orderly.py`). Fills are simulated
  against the live public tape; spread vs directional PnL decomposed.
- **Tape validation** (`validate_runner.py` + `shadow_logger.py`): collect
  real prints against your shadow ladder; a parameter-free crossing rule with
  a queue cap scores the fill model on data it never saw. Gate: ≥200 fills
  and ≥2 days before dollar numbers get the "validated" label.

No custody, no API keys for any core feature. All data sources are free
public endpoints (Hyperliquid info API, Pyth Benchmarks, Orderly public API).

## Required env

None. Optional (see `.env.example`): `PORT`, `COINGLASS_SKILL_DIR`,
`ORDERLY_BASE`.

## How to start

```bash
pip install flask requests
cd src && python3 app.py        # serves on :7011 (or $PORT)
```

Open the dashboard, pick an asset (or fetch a new one), tweak the strategy
config, hit Run. The trust panel tells you how much to believe the output.

Paper-live (no keys):

```bash
cd src && python3 paperlive_orderly.py --symbols PERP_ETH_USDC --side 30000
```

Shadow tape collection for validation:

```bash
cd src && python3 shadow_logger.py --symbol <ORDERLY_SYMBOL> --side-notional 30000
cd src && python3 validate_runner.py --score --coin <COIN>
```

## Outputs

- `src/fetched/` — cached OHLC for fetched assets (created at runtime)
- `src/paper/` — paper-live session state, fills, shadow quotes
- `src/shadow/` — shadow-ladder tape + fills for validation
- API: `GET /api/assets`, `POST /api/run`, `POST /api/fetch`,
  `GET /api/paper/status`, `POST /api/paper/start|stop`, `GET /api/tape`

## Troubleshooting

- **"no oracle candle data"** — asset not listed on Hyperliquid main universe;
  builder-dex assets (`xyz:...`) need the dex param and may have thin tape.
- **Pyth fetch empty / 429** — Benchmarks rate-limits hard; retry after a few
  seconds. RWA feeds only print during market hours, vol is annualized on the
  asset's own bars/day to compensate.
- **Exchange list shows only 3 entries** — CoinGlass skill not found at
  `COINGLASS_SKILL_DIR`; the Hyperliquid + Pyth paths are unaffected.
- **Trust score stays 0** — that's the design. Collect real tape with the
  shadow logger until the gate (≥200 fills, ≥2 days) clears; only then do
  dollar estimates earn the validated label.
