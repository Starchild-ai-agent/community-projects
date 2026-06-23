# WOOFi Pro Trading Agent

Automated trading agent for WOOFi Pro perpetual futures (Orderly Network infrastructure).

## ⚠️ Status: BUILD PHASE — NOT TRADING

This agent is under construction. No live orders will be placed until:
1. Account ID is confirmed
2. Risk parameters are reviewed and approved by the user
3. Strategy is backtested / paper-traded
4. User gives explicit "go live" approval

## Account

- **Balance:** $20 USDC (deposited)
- **Exchange:** WOOFi Pro (Orderly Network omnichain CLOB)
- **API Auth:** ed25519 key/secret + Orderly Account ID
- **Credentials:** stored in `workspace/.env` (WOOFI_API_KEY, WOOFI_API_SECRET)
- **Missing:** WOOFI_ACCOUNT_ID — required for signed requests

## Key Facts (verified from Orderly API + WOOFi docs)

### Infrastructure
- WOOFi Pro runs on **Orderly Network** — omnichain orderbook DEX
- API base: `https://api.orderly.org` (mainnet)
- Auth: ed25519 signature, headers: `orderly-account-id`, `orderly-key`, `orderly-signature`, `orderly-timestamp`
- Symbol format: `PERP_<TOKEN>_USDC` (e.g. `PERP_BTC_USDC`)
- 127 active perp markets
- Cross-margin only (USDC collateral shared across positions)
- One-sided mode (no simultaneous long+short on same symbol)
- Max account leverage: 1x–100x (adjustable); per-contract leverage tiers: 1x, 2x, 3x, 4x, 5x, 10x, 20x, 50x
- Gasless trading once keys activated
- CCXT integration available (`woofipro`)

### Fees (WOOFi Pro)
- Maker fee: negative (rebate) for limit orders that add liquidity
- Taker fee: charged on market orders
- Fee tiers boosted by staking WOO; 30-day volume also climbs tiers
- Fees charged in USDC, added to cost position
- Check your tier: https://pro.woofi.com/en/portfolio/fee

### Funding
- Funding interval: **every 8 hours** (next funding timestamps visible in market data)
- BTC current est. funding: ~0.01% per 8h (longs pay shorts) → ~0.03%/day
- ETH current est. funding: ~0.01% per 8h
- SOL current est. funding: ~0.0016% per 8h (near neutral)
- Funding can flip negative (shorts pay longs) — seen on BTC earlier in the week

### Risk Mechanics
- **Initial Margin (IM):** required to open position = notional / leverage
- **Maintenance Margin (MM):** minimum to avoid liquidation
- **Mark Price:** used for liquidation (less volatile than index/last)
- **Liquidation:** forced close when margin < MMR
- **ADL (Auto-Deleveraging):** backstop if liquidation engine fails
- **Insurance Fund:** covers liquidation gaps

## Current Market Snapshot (2026-06-22 UTC)

| Symbol | Price | 24h Range | 24h Vol (USD) | Est Funding | OI |
|--------|-------|-----------|---------------|-------------|----|
| BTC | $65,002 | $63,221–$65,568 | $58.1M | +0.01%/8h | 107.6 BTC |
| ETH | $1,753 | $1,701–$1,778 | $7.4M | +0.01%/8h | 15,307 ETH |
| SOL | $73.44 | $72.24–$74.92 | $2.0M | +0.0016%/8h | 25,796 SOL |

### BTC 14-day price action
- Range: $60,708 (06-09 low) → $67,248 (06-15 high) → current $65,002
- Down ~3.3% from 06-15 high, up ~7% from 06-09 low
- Choppy / range-bound with slight downward drift last 7 days
- Funding flipped negative briefly on 06-17, now positive again

### Macro context (June 2026)
- Coinbase Institutional: "cautiously optimistic" — setup rhymes with 1996 not 1999
- Fed rate cut expectations influencing risk sentiment; no aggressive easing yet
- ETF flows volatile (saw outflows early June)
- Regulatory clarity improving (2025 landmark advances)
- Institutional adoption via Digital Asset Treasuries (DATs) expanding
- Market ~25-30% off recent peaks per some sources; BTC dominance rising

## Proposed Risk Parameters (DRAFT — needs user approval)

Given $20 starting balance, the priority is **capital preservation**.

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Max account leverage | **3x** | Low; liquidation distance ~33% |
| Per-trade risk | **2% of equity** ($0.40) | Standard conservative risk per trade |
| Max concurrent positions | **2** | Limits correlation risk |
| Max daily loss | **5% of equity** ($1.00) | Circuit breaker |
| Max weekly loss | **10% of equity** ($2.00) | Hard stop, review |
| Default position leverage | **2x** | Conservative |
| Stop-loss | **Required** on every position | No naked positions |
| Min R:R | **1.5:1** | Only take trades with positive expectancy |
| Margin mode | Cross | Only mode available |
| Order type preference | **Limit (maker)** | Capture fee rebate, avoid slippage |

## Proposed Strategy Approach (DRAFT)

For a $20 account on a choppy/range-bound market:

### Phase 1: Observation (1-2 weeks)
- Paper trade / log signals without capital
- Track funding rates, OI changes, orderbook imbalance
- Build market structure read (Wyckoff / SMC levels)

### Phase 2: Conservative execution
- **Mean-reversion** in identified ranges (buy support, sell resistance)
- **Funding arbitrage** when funding is extreme (e.g. >0.03%/8h → fade the crowd)
- **Breakout confirmation** with volume (avoid false breakouts in chop)
- Position size: 0.5–1% risk per trade → $0.10–$0.20 actual risk

### What to AVOID with $20:
- High leverage (>5x) — one bad trade = account blown
- Funding-heavy longs when funding is elevated
- Chasing pumps in low-liquidity alts
- Overtrading (fees eat small accounts alive)

## File Structure

```
projects/woofi-agent/
├── README.md              # This file
├── config/
│   ├── risk.yaml          # Risk parameters (DRAFT)
│   └── strategy.yaml      # Strategy config (DRAFT)
├── src/
│   ├── client.py          # Orderly API client (ed25519 auth)
│   ├── market_data.py     # Market data fetchers
│   ├── risk.py            # Risk engine / position sizing
│   ├── strategy.py        # Strategy logic
│   └── agent.py           # Main agent loop
└── logs/
```

## Next Steps

1. **User provides Account ID** → enable authenticated API calls
2. **Review & approve risk parameters** above
3. **Build client.py** — signed API wrapper (read-only first)
4. **Verify account state** — confirm $20 balance, fee tier, leverage setting
5. **Build market data module** — funding, OI, orderbook, candles
6. **Build risk engine** — position sizing, circuit breakers
7. **Paper trade** — log signals, no orders
8. **Review** → user approves → go live with smallest possible size
