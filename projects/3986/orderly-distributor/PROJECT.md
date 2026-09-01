# Orderly Distributor Program v2 — Mechanics Spec

## What

A single self-contained HTML page (`site/index.html`, no build step, no dependencies)
presenting the v2 distributor program design, plus `model.py`, which regenerates every
table in the spec.

**The design in one line:** rate is bought with ORDER staking, status is earned with
volume, and a capacity mechanic ties the correct stake size to how well the distributor
is performing — so staking demand grows with the program instead of saturating at the
top tier.

| Path | What it is |
|---|---|
| `site/index.html` | The spec as a web page, including a live capacity simulator (§04) |
| `SPEC.md` | The same content in markdown |
| `model.py` | Regenerates every table in the spec |

## Required env

None. The page is static HTML with inline CSS/JS and no API calls; `model.py` uses only
the Python standard library. `.env.example` is intentionally empty.

## How to start

```
python3 -m http.server 9083 --directory site
```

Then open `http://localhost:9083/`. To reprint every table from the model:

```
python3 model.py
```

## Outputs

- A one-page spec site, §00 (locked decisions) through §11 (decisions closed).
- An interactive capacity simulator in §04: volume slider × stake tier, showing revenue,
  payout, effective rate, the inside-capacity/overflow split, and how much additional
  ORDER closes the gap. Its arithmetic mirrors `model.py` exactly.
- `model.py` prints the stake ladder, upgrade ROI, capacity behaviour, sponsorship
  indifference, program cost and staking-demand tables to stdout.

## Troubleshooting

- **Tables and simulator disagree** — one side was edited alone. `TIERS`, `CAP_PER_ORDER`
  (0.25), `BPS` (3.00) and `PRICE` appear in both `model.py` and the inline script in
  `site/index.html`; change both.
- **Numbers look stale** — the reference ORDER price is $0.0331 (CoinGecko, 2026-09-01).
  Update `ORDER_PRICE` in `model.py`, re-run, and paste the refreshed USD columns in.
- **Simulator shows no overflow** — expected below capacity. Vanguard (7M ORDER) covers
  $1.75M of monthly revenue ≈ $5.8B of monthly taker volume at 3 bps; push past that to
  see the effective rate decay.
- **Port 9083 already in use** — pass any other port to `http.server`; nothing is
  hard-coded to it.
