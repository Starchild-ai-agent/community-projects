# WOOFi Pro Trading Agent

Automated trading agent for **WOOFi Pro** perpetual futures (powered by Orderly Network). Designed for small accounts ($20–$100) with capital preservation as the top priority.

## What it does

- **Strategy:** Mean reversion with funding filter — fades range extremes when funding rates suggest the crowd is overcrowded.
- **Markets:** BTC, ETH, SOL perpetuals (USDC-settled, cross-margin).
- **Risk management:** Position sizing based on % risk per trade, mandatory stop-loss + take-profit on every position, daily/weekly loss circuit breakers, max concurrent position cap.
- **Order execution:** Limit entries (maker fee), algo-based stop-loss and take-profit (reduce-only), max-hold time exit, range-break exit.
- **Notifications:** Pushes to your Telegram/Feishu/Web when trades open, close, or the agent halts.

## How the strategy works

1. **Range detection:** Looks at the last 50 hourly candles. Requires ≥2 touches on both support and resistance to confirm a real range (not a trend).
2. **Entry triggers:**
   - **Long:** Price in bottom 20% of range + RSI < 40 (oversold)
   - **Short:** Price in top 20% of range + RSI > 60 (overbought)
3. **Orderbook confirmation:** Bid/ask imbalance must align with direction (e.g. longs need more bids than asks).
4. **Funding filter:** Skips longs if funding > 10bps (crowded longs = reversion risk). Skips everything if funding > 20bps (extreme).
5. **Exit rules:**
   - Stop-loss at 1.5×ATR
   - Take-profit at 2.0×ATR (R:R ≈ 1.33:1)
   - Max hold: 24 hours (avoids funding bleed)
   - Exit if price breaks the range (mean reversion failed)

Most hours, the agent does nothing — and that's correct. It only fires when all conditions align.

## Required env

| Variable | Description |
|----------|-------------|
| `WOOFI_API_KEY` | Orderly ed25519 public key (with `ed25519:` prefix) |
| `WOOFI_API_SECRET` | Orderly ed25519 private key (with `ed25519:` prefix) |
| `WOOFI_ACCOUNT_ID` | Orderly account ID (hex, starts with `0x`) |

Get all three from [WOOFi Pro → Portfolio → API Key](https://pro.woofi.com/en/portfolio/api-key).

## How to start

1. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your API key, secret, and account ID
   ```

2. **Install dependencies:**
   ```bash
   pip install cryptography base58 pyyaml requests
   ```

3. **Test the connection:**
   ```bash
   cd src && python3 client.py
   ```
   You should see your account info and BTC market data.

4. **Run once manually:**
   ```bash
   cd src && python3 agent.py
   ```
   It will evaluate signals and place trades if conditions are met.

5. **Schedule as a cron job** (every 10 minutes recommended):
   ```bash
   # In your agent's scheduled task system, or crontab:
   */10 * * * * cd /path/to/woofi-trading-agent/src && python3 agent.py
   ```

## Configuration

### Risk parameters (`config/risk.yaml`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `risk_per_trade_pct` | 2.0 | % of equity risked per trade |
| `max_account_leverage` | 3 | Hard ceiling on leverage |
| `max_concurrent_positions` | 2 | Max positions open at once |
| `max_daily_loss_pct` | 5.0 | Daily loss circuit breaker |
| `max_weekly_loss_pct` | 10.0 | Weekly loss circuit breaker |
| `allowed_symbols` | BTC/ETH/SOL | Whitelist of tradeable markets |

### Strategy parameters (`config/strategy.yaml`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `range_lookback` | 50 | Candles to define the range |
| `min_range_touches` | 2 | Min touches on support/resistance |
| `rsi_oversold` | 40 | RSI threshold for long entries |
| `rsi_overbought` | 60 | RSI threshold for short entries |
| `stop_loss_atr_mult` | 1.5 | Stop distance in ATR multiples |
| `take_profit_atr_mult` | 2.0 | Target distance in ATR multiples |
| `max_hold_hours` | 24 | Max position hold time |

## Outputs

- `logs/signals.log` — Every signal evaluation (trade or skip, with reason)
- `logs/trades.log` — Every order placed (entry, stop, target, exit)
- Push notifications — Sent to your configured channels when trades open/close

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `invalid request signature` | API secret is wrong or missing the `ed25519:` prefix |
| `orderly-account-id header is empty` | `WOOFI_ACCOUNT_ID` env var not set |
| No trades happening | Normal — the strategy is selective. Check `logs/signals.log` to see why signals are being skipped |
| Stop-loss not placing | Check that your API key has "Trading" permission (not just "Read") |
| Position too large | Lower `risk_per_trade_pct` in `config/risk.yaml` |

## ⚠️ Risk disclaimer

This is trading software. You can lose money. The strategy is designed to be conservative, but:

- **Test on a small amount first** — don't deploy with money you can't afford to lose.
- **Lower your account leverage** on WOOFi Pro's portfolio page (3x recommended) as a safety net.
- **Monitor the first few trades** to make sure the agent behaves as expected.
- **Past performance ≠ future results.** Mean reversion can fail in trending markets.

## Architecture

```
agent.py (runs every 10 min)
  ├─ Check circuit breakers (daily/weekly loss limits)
  ├─ Manage open positions (max-hold exit, range-break exit)
  ├─ Evaluate signals for BTC/ETH/SOL
  ├─ On TRADE signal:
  │   ├─ Risk engine sizes position
  │   ├─ Place LIMIT entry (maker fee)
  │   ├─ Place STOP-LOSS algo order (reduce-only)
  │   └─ Place TAKE-PROFIT algo order (reduce-only)
  └─ Push notification to user
```

## License

MIT — do whatever you want, just don't blame me if you lose money.
