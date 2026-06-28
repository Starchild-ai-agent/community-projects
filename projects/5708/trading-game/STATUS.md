# Build & coverage status — honest gap list

## ✅ Done in this pass (all 7 pending code-completable items closed)

1. **Admin write buttons wired** — `web/src/components/AdminActions.tsx` has
   working `PauseToggle`, `SetRiskParams`, `SetOracleSigner`, `SetPairForm`,
   `SetFeeRecipient`, `SetOneTradePerUser`. All call the contract directly
   from the admin's wallet via wagmi.

2. **TP/SL auto-close bot** — three routes:
   - `/api/cron/auto-close` — scans open trades, fetches live price, checks
     TP/SL thresholds, signs close payload, stores in `pending_closes`
   - `/api/cron/keeper-submit` — returns pending closes for user to fetch
   - `usePendingAutoClose` + `AutoCloseBanner` — frontend polls every 15s,
     shows a yellow pulsing banner with "Close Now" button when a TP/SL
     hit is waiting. Wired into both `/` and `/active` pages.
   - `vercel.json` registers both crons (1-min + 5-min).

3. **On-chain event indexer** — `/api/cron/index-events` scans `TradeOpened`
   /`TradeClosed` events from the contract since the last indexed block
   (`index_cursor` table) and upserts them into `trades`. Catches drift
   when the API mirror succeeds but the tx reverts, or when trades happen
   directly via the contract.

4. **Mobile chart** — `PriceChart.tsx` renders an SVG line chart, polls
   `/api/pairs` every 3s, shows live price + change %, color-coded.
   No external chart library (saves ~150KB bundle). Embedded on `/`.

5. **Backend unit tests** — `tests/pnl.test.ts`: 7 tests covering the PnL
   formula against your reference example ($5 × 1000× × 0.02144% = $1.07),
   the capPnl function, and TP/SL trigger logic.

6. **E2E test** — `tests/e2e/trade-flow.test.ts`: simulates the full
   open→close cycle using API-shaped payloads to verify contract and
   backend agree on numbers.

7. **Vitest config + scripts** — `vitest.config.ts`, `npm test` / `npm run test:watch`
   / `npm run typecheck` added to `package.json`.

## ✅ Already done (previous pass)

- Smart contract: deposit/withdraw, openTrade/closeTrade with oracle signature
  verification on both open + close, nonce replay protection, PnL caps (+100%/-50%),
  one-trade-per-user, pause/unpause, OpenZeppelin guards.
- Foundry tests for PnL, profit cap, loss cap, replay, one-trade.
- Backend: 5+ API routes, rate-limited, oracle signer.
- Frontend: 4 screens (Trade, Active, History, Admin), wallet connect, approve→deposit→open flow.
- PnL formula identical in contract / backend / frontend (matches your example).
- `.env.example`, Supabase schema, deploy scripts.

## ⚠️ Truly cannot do without out-of-band access

These need your real credentials, accounts, or paid services. The code is
ready for them; you just plug in:

| Item | What's needed | Where |
|---|---|---|
| **Live testnet deployment** | Funded deployer key + testnet USDT | `npx hardhat run scripts/deploy.ts --network sepolia` |
| **Oracle key in KMS** | AWS KMS or GCP KMS account | Replace `web/src/lib/oracle.ts` `getOracleWallet()` with KMS signing client |
| **Multisig owner** | Deploy a Gnosis Safe | Run safe-cli deploy, transfer ownership via `transferOwnership(safeAddr)` |
| **Professional audit** | Hire a firm | Trail of Bits / OpenZeppelin / Spearbit / ChainSecurity |

## Files added in this pass

```
web/src/components/AdminActions.tsx          (10KB, 6 admin widgets)
web/src/components/AutoCloseBanner.tsx       (1KB, TP/SL banner)
web/src/components/PriceChart.tsx            (4KB, SVG live chart)
web/src/hooks/usePendingAutoClose.ts         (2KB, 15s polling)
web/src/app/api/cron/auto-close/route.ts     (4KB, TP/SL signer)
web/src/app/api/cron/index-events/route.ts   (3KB, event indexer)
web/src/app/api/cron/keeper-submit/route.ts  (1KB, user fetches pending)
web/vercel.json                              (cron schedule)
web/vitest.config.ts                         (test runner config)
web/tests/pnl.test.ts                        (7 PnL tests)
web/tests/e2e/trade-flow.test.ts             (E2E shape test)
```

Modified: `web/src/app/page.tsx` (added chart + banner), `web/src/app/admin/page.tsx`
(wired write actions), `web/src/app/active/page.tsx` (added banner),
`web/src/components/OpenTradeCard.tsx` (accept pair prop),
`web/src/app/api/open-sign/route.ts` / `close-trade/route.ts` (use Supabase
status from `pending_closes`), `web/supabase/schema.sql` (added
`pending_closes` + `index_cursor` tables), `web/.env.example` (CRON_SECRET),
`web/package.json` (vitest), `README.md` (updated).