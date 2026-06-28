# TradingGame — 1000x Perp Trading Platform

A full-stack Web3 leveraged up/down trading game with on-chain settlement.

```
trading-game/
├── contracts/        Solidity + Hardhat + Foundry tests
└── web/              Next.js 14 (frontend + API routes) + Supabase
```

## Architecture

```
User (browser) ──► Next.js API ──► Price oracle (Binance/CoinGecko)
     │                  │
     │                  └──► Signs price with ORACLE_PRIVATE_KEY (backend only)
     │                  └──► Mirrors trade to Supabase
     │
     └──► TradingGame.sol (on-chain settlement)
              │ verifies oracle signature (ecrecover)
              │ locks/releases margin (SafeERC20)
              │ caps PnL (+100% / -50%)
```

**Security model:** the contract NEVER trusts a frontend price. Both `openTrade`
and `closeTrade` require a backend signature over the price + timestamp + nonce.
The contract verifies the sig with `ecrecover` before settling. Close payloads
carry a nonce burned on use → replay-proof.

## PnL formula (identical in contract, backend, and frontend)

```
priceMovePct = ((close - open) / open) * 100      [UP]
priceMovePct = ((open - close) / open) * 100      [DOWN]
leveragedROI = priceMovePct * leverage
pnl          = margin * leveragedROI / 100
```

Example: margin $5, leverage 1000×, open 72.7349, close 72.7193, DOWN
→ priceMove 0.02144% → ROI 21.44% → profit $1.07

## Quick start

### 1. Install

```bash
cd contracts && npm install
cd ../web && npm install
```

### 2. Env setup

```bash
cp web/.env.example web/.env.local
# fill in:
#   ORACLE_PRIVATE_KEY        (generate via step 3)
#   ORACLE_SIGNER_ADDRESS     (derived from the key above)
#   DEPLOYER_PRIVATE_KEY
#   NEXT_PUBLIC_RPC_URL
#   MARGIN_TOKEN_ADDRESS
#   SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY
#   ADMIN_WALLETS
#   CRON_SECRET               (any random string)
```

### 3. Generate oracle signer + deploy contract

```bash
cd contracts
npx hardhat run scripts/gen-oracle-key.ts          # → prints address + private key
# put those into web/.env.local

npx hardhat run scripts/deploy.ts --network sepolia
# → prints deployed address, enables SOL/BTC/ETH pairs,
#   writes ABI to web/src/lib/contract.generated.ts
#   sets NEXT_PUBLIC_TRADING_GAME_ADDRESS in web/.env.local
```

### 4. Run Supabase schema

Run `web/supabase/schema.sql` in the Supabase SQL editor. This creates:
- `trades` — trade mirror with RLS
- `pending_closes` — signed payloads waiting for user submission
- `index_cursor` — event indexer block cursor
- `pairs` + `risk_params` — admin-configurable settings

### 5. Run frontend

```bash
cd web
npm run dev      # http://localhost:3000
npm test         # vitest (pnl + e2e)
npm run typecheck
```

### 6. Deploy to Vercel

```bash
cd web
vercel --prod
# Set env vars in Vercel dashboard (Project → Settings → Environment Variables).
# The included vercel.json registers two cron jobs:
#   - /api/cron/auto-close     every 1 min   — scans open trades, signs TP/SL closes
#   - /api/cron/index-events   every 5 min   — reconciles on-chain events → Supabase
```

## Endpoints

| Route | Method | Auth | Purpose |
|---|---|---|---|
| `/api/price` | GET | — | Live price for a pair |
| `/api/pairs` | GET | — | All pairs + prices |
| `/api/open-sign` | POST | — | Signs open price (oracle key) |
| `/api/close-trade` | POST | — | Signs close price + nonce |
| `/api/history` | GET | — | Trade history (Supabase) |
| `/api/cron/auto-close` | POST | Bearer `CRON_SECRET` | Cron: scans for TP/SL hits, signs close payloads |
| `/api/cron/index-events` | POST | Bearer `CRON_SECRET` | Cron: scans contract events → Supabase |
| `/api/cron/keeper-submit` | GET | Bearer `CRON_SECRET` | User polls this to find pending auto-closes |

## Frontend routes

| Route | Purpose |
|---|---|
| `/` | Trade screen — pair tabs, live SVG chart, open trade card |
| `/active` | Active trade inspector + auto-close banner |
| `/history` | Trade history table |
| `/admin` | Admin dashboard (gated by `ADMIN_WALLETS`): pause, risk params, oracle signer, pair config |

## Risk rules (enforced in contract)

| Rule | Default | Hard cap |
|---|---|---|
| Max profit | +100% of margin | +100% (immutable) |
| Max loss | -50% of margin | -50% (immutable) |
| Max leverage | 1000× | 1000× (immutable) |
| Platform fee | 1% of margin | ≤ 50% |
| One active trade per user | yes | toggle by admin |
| Price freshness | ≤ 60s | enforced in contract |

## What is NOT done

See `STATUS.md`. Three items genuinely require out-of-band access:
- **Real testnet deployment** — needs your funded deployer key + testnet USDT
- **KMS for oracle key** — needs your AWS/GCP KMS setup
- **Multisig owner** — needs you to deploy a Gnosis Safe and transfer ownership
- **Professional audit** — hire Trail of Bits / OpenZeppelin / Spearbit