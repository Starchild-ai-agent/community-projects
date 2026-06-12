# QuoteSim — bring-your-own-asset market-making simulator

**One-liner:** Point it at any asset, hand it a quoting config, get back a PnL
decomposition — *stamped with a trust score that tells you whether to believe it.*

The moat isn't the simulator. Anyone can write a candle backtest. The moat is
the **trust gate**: the tool calibrates against a book we have ground truth for,
scores its own reliability, and refuses to hand you a fake number.

## Who it's for
Starchild users who want to MM a market (their own Orderly listing, a perp,
anything) and need to answer two questions before risking capital:
1. Is there repeatable spread edge here, or am I just taking directional risk?
2. How big does inventory get, and how hard does it bite at this asset's vol?

## Architecture (all config-driven, asset-agnostic)
```
AssetConfig      symbol, oracle sources/weights, tick/lot, maker/taker fees
StrategyConfig   side notional, n_levels, min/band bps, inventory tiers,
                 close_skew, soft-reset   ← the entire user form
        │
        ▼
   Engine        builds ladder → asks fill model what filled →
                 inventory/avg-cost state machine →
                 PnL split: spread | directional | fees
        │
        ▼
   FillModel  ── OHLCTouchFill   fast, rough, free (bar-touch). trust: low.
              └─ TapeReplayFill  real trade tape + queue depth. trust: high.
        │
        ▼
   Validator     calibrate on a ground-truth asset → trust_score 0-100 + verdict
```

Swap the asset → swap one JSON block. Swap the strategy → swap another. The
engine, fill models, and validator never change.

## The trust gate (why this is honest, not slop)
Before showing any number for the user's target asset, the engine runs on a
**ground-truth asset** (NATGAS — we have live measured PnL) and scores how well
it reproduces reality. Output is 0-100:
- **75-100 TRUSTWORTHY** — believe the dollars.
- **45-74 DIRECTIONAL ONLY** — trust the shape (risk profile), not the $.
- **0-44 UNRELIABLE** — the cheap model can't price this regime; run the
  validated TapeReplay shadow logger.

### Live demo result (this build)
- NATGAS vol ≈ 54%, VVV vol ≈ 208% (5-min bars).
- OHLC model calibrated on NATGAS scored **0/100** — it overcounts fills ~23×
  and flips the directional sign. **Correctly refused** to vouch for VVV's
  −$205/day figure.
- **Key finding:** `fill_eff` scales fill *size*, not *count* — so a bar-touch
  model can NEVER match real fill frequency. That structural gap is itself the
  proof that an honest product needs the tape model, and is exactly what the
  trust score surfaces automatically.

## Roadmap to ship
1. **MVP (done):** config objects, engine, OHLC fill model, trust gate, demo.
2. **Validated fill model (built; validated honestly):** `TapeReplayFill` +
   `shadow_logger.py`. Real NATGAS validation on 96h public tape (183 prints,
   53 maker fills): **structural prediction strong** — fill count within 13%,
   filled volume within 12%, **zero tuned parameters** (vs OHLC's 22× overcount
   needing a fudge factor). **Score 52/100 "DIRECTIONAL ONLY"** — the dollar
   term is noise-dominated on a 4-day / 53-fill window, and the public tape
   endpoint caps at ~183 prints. Path to ≥75 = run `shadow_logger.py` for
   multi-day collection (stabilizes the dollar term) + model taker fills.
   The score was NOT engineered up; the honest verdict is the product working.
3. **Data adapters:** pull OHLC/tape for any symbol (CoinGlass/Binance/Bybit/HL)
   from the user's chosen oracle sources.
4. **Preview dashboard (done; live):** config form → run → trust badge +
   PnL decomposition + inventory-excursion chart. `/preview/2195-quotesim-dashboard/`
   Publishable per-user via community-publish.
5. **Skill wrapper:** `quotesim` skill so any agent can run it from chat.

## New files (steps 2 & 4)
- `shadow_logger.py` — deployable live tape + dry-quote collector for any symbol
- `quotesim/tape_validate.py` — tape-replay crossing model + honest scoring
- `fetch_validation_data.py` — pulls NATGAS tape/fills/telemetry ground truth
- `app.py` + `dashboard.html` — Flask-backed config→trust-badge dashboard
- `valdata/` — NATGAS ground-truth dataset · `tape_validation.json` — result

## Files
- `quotesim/config.py` — user-facing config (AssetConfig, StrategyConfig)
- `quotesim/engine.py` — ladder + inventory + PnL decomposition
- `quotesim/fillmodels.py` — OHLCTouchFill (now) / TapeReplayFill (interface)
- `quotesim/validate.py` — calibrate + trust_score
- `run_demo.py` — end-to-end on NATGAS (truth) → VVV (target)
