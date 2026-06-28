# TradingGame — 1000x Perp Trading Platform

## What

A full-stack Web3 leveraged up/down trading game with **on-chain settlement**. Users connect a wallet, pick a pair (SOL/BTC/ETH perp), choose UP or DOWN, post margin, and the platform applies fixed 1000× leverage. Profit/loss is settled on-chain against an oracle-signed close price — the contract never trusts a frontend-submitted price.

**Stack:** Solidity (Hardhat + Foundry) · Next.js 14 (app router) · wagmi + RainbowKit · Supabase · Tailwind

### PnL formula (identical in contract / backend / frontend)

```
priceMovePct = ((close - open) / open) * 100      [UP]
priceMovePct = ((open - close) / open) * 100      [DOWN]
leveragedROI = priceMovePct * leverage
pnl          = margin * leveragedROI / 100
```

Example: $5 margin × 1000× leverage, open 72.7349, close 72.7193, DOWN → +$1.07 (21.44% ROI).

### Security model

- Contract NEVER trusts frontend price — both `openTrade` and `closeTrade` require a backend oracle signature (EIP-191) verified with `ecrecover`.
- Close payloads carry a nonce burned on use → replay-proof.
- Margin is real ERC20 locked in the contract via SafeERC20 + ReentrancyGuard.
- PnL caps enforced in-contract: +100% profit / -50% loss (immutable hard caps).
- Price freshness check (≤ 60s) in contract.
- One active trade per user (admin-toggleable).
- Rate limiting on all API routes.

## Required env

Copy `web/.env.example` → `web/.env.local` and fill in. Full list in `.env.example`. Critical:

| Var | Purpose |
|---|---|
| `DEPLOYER_PRIVATE_KEY` | Funds contract deploy (Sepolia ETH) |
| `ORACLE_PRIVATE_KEY` | Backend signs prices with this; address must match contract's `oracleSigner` |
| `NEXT_PUBLIC_RPC_URL` | Sepolia RPC endpoint |
| `NEXT_PUBLIC_TRADING_GAME_ADDRESS` | Set automatically by deploy script |
| `NEXT_PUBLIC_MARGIN_TOKEN_ADDRESS` | Testnet USDT or mock ERC20 |
| `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` | Backend mirror |
| `ADMIN_WALLETS` | Comma-separated admin addresses |
| `CRON_SECRET` | Bearer token for `/api/cron/*` routes |
| `NEXT_PUBLIC_WC_PROJECT_ID` | From cloud.reown.com |

## How to start

### 1. Install

```bash
cd contracts && npm install
cd ../web && npm install
```

### 2. Env

```bash
cp web/.env.example web/.env.local
# fill in oracle key, deployer, RPC, Supabase, admin wallets, cron secret
```

### 3. Generate oracle signer + deploy contract

```bash
cd contracts
npx hardhat run scripts/gen-oracle-key.ts          # prints address + private key
# put those into web/.env.local

npx hardhat run scripts/deploy.ts --network sepolia
# deploys contract, enables SOL/BTC/ETH pairs, writes ABI to web/src/lib/contract.generated.ts
```

### 4. Supabase schema

Run `web/supabase/schema.sql` in the Supabase SQL editor. Creates `trades`, `pending_closes`, `index_cursor`, `pairs`, `risk_params` tables with RLS.

### 5. Frontend

```bash
cd web
npm run dev          # http://localhost:3000
npm test             # vitest (pnl + e2e)
npm run typecheck
```

### 6. Deploy to Vercel

```bash
cd web && vercel --prod
# set env vars in Vercel dashboard; vercel.json registers the two cron jobs
```

### 7. Tests

```bash
cd contracts && forge install && forge test -vvv   # Foundry (5 tests)
cd web && npm test                                   # Vitest (7+ tests)
```

## Outputs

- `contracts/` — Solidity contract + Hardhat deploy + Foundry tests
- `web/` — Next.js app (frontend + API routes + cron jobs)
- `web/supabase/schema.sql` — database schema
- `web/src/lib/contract.generated.ts` — auto-written ABI on deploy

## Troubleshooting

| Symptom | Fix |
|---|---|
| `contract not deployed` in API | Run `npx hardhat run scripts/deploy.ts --network sepolia` first |
| `oracle signer mismatch` | `ORACLE_PRIVATE_KEY` derived address ≠ contract's `oracleSigner` — regenerate or call `adminSetOracleSigner` |
| WalletConnect modal empty | Set `NEXT_PUBLIC_WC_PROJECT_ID` from cloud.reown.com |
| Cron routes 401 | Set `CRON_SECRET` and configure Vercel cron auth header |
| `bad open sig` on contract | Price timestamp > 60s old — check server clock sync |
| Supabase RLS blocks reads | Service-role key bypasses RLS; anon key needs the `own trades read` policy |

## Limitations (honest gaps)

See `STATUS.md` for the full gap list. Items requiring out-of-band access:
- Live testnet deployment (needs funded deployer key)
- KMS for oracle key (needs AWS/GCP KMS)
- Multisig owner (needs Gnosis Safe)
- Professional audit (hire a firm)
