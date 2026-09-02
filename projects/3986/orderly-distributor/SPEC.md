# Orderly Distributor Program — Mechanics

**Status:** draft for review · **Date:** 2026-09-01
**Reference price:** ORDER $0.0331 (CoinGecko, 2026-09-01) · mcap $13.5M · 409.5M circulating · FDV $33.1M

---

## 0. Decisions locked from your answers

| # | Decision |
|---|---|
| Gate | Application, approved by BD. Approval test = *can this applicant actually deliver volume* |
| Payout base | **Orderly's own base-fee revenue** from the recruited builder. Taker only (Orderly charges taker only) |
| Rate | 10% floor on approval → 50% ceiling |
| Tier driver | **ORDER staking only.** Volume never affects anything — no rate threshold, no cap, no decay, no status ladder |
| Duration | Perpetual for the life of the recruited DEX |
| Migration | Force-migrate every existing distributor |
| Depth | Flat, one level. No sub-distributors |
| Target profile | Anyone with access to people who might launch a DEX or bolt perps onto an existing product (wallet apps, trading communities, agencies, regional partners) |

---

## 1. The model

A distributor recruits a DEX onto Orderly. Orderly earns a base taker fee from that DEX. The distributor takes a share of that fee for the life of the DEX.

The share is set by one input: **how much ORDER the distributor has staked.** It runs from 10% at zero stake to 50% at the top of the ladder. Nothing else moves it — not volume, not tenure, not the number of DEXs recruited. Volume determines how much revenue exists to share; it never changes the percentage.

This gives Orderly a single policy dial it controls directly, and gives distributors one clear reason to hold the token.

---

## 2. Payout formula

```
Billed_Taker_Notional(builder, day) = notional on which Orderly billed a base taker fee

Payout = Share%(distributor stake tier) × Notional_Revenue
         − Sponsorship_Discount_Cost
         (floored at 0)

where Notional_Revenue = Billed_Taker_Notional × 3.00 bps   (the Public rate)
```

**Volume means the notional the fee engine billed, not a reported volume figure.** Orderly charges a base fee on the taker side only and every match has exactly one taker side, so this is single-sided by construction and cannot drift with how analytics reports volume. Every number in this document is computed on that definition.

Two deliberate choices:

- **Share applies to *notional* revenue at 3 bps, not actual.** If the invitee earns a cheaper rate through their *own* volume or staking, the distributor is not punished for their builder succeeding.
- **If the cheaper rate came from *distributor sponsorship*, the full discount is debited from the distributor's payout.** See §5 — this makes Orderly exactly indifferent to sponsorship, so it can be handed out as a closing tool without a revenue committee.

Maker fees, maker rebates, and liquidation fees are out of scope (Orderly charges no maker base fee). RWA and crypto are treated identically, matching the builder table.

---

## 3. Stake ladder (the rate dial)

| Tier | ORDER staked | USD @ $0.0331 | Share of Orderly rev | Applies to |
|---|---|---|---|---|
| Registered | 0 | $0 | 10% | all attributed revenue |
| Silver | 100,000 | $3,310 | 18% | all attributed revenue |
| Gold | 300,000 | $9,930 | 26% | all attributed revenue |
| Platinum | 1,000,000 | $33,100 | 34% | all attributed revenue |
| Diamond | 3,000,000 | $99,300 | 42% | all attributed revenue |
| Vanguard | 7,000,000 | $231,700 | 50% | all attributed revenue |

Thresholds deliberately reuse the Builder Staking anchors (100K / 300K / 3M / 7M) so the ecosystem has **one ORDER ladder**, with 1M inserted to smooth the 300K→3M cliff. Steps are a uniform +8% so every upgrade is a clean ROI question.

**Upgrade ROI** — each +8% step is worth $2,400 per $100M of monthly taker volume:

| Upgrade | Extra ORDER | Extra USD | Cumulative taker volume to repay the stake |
|---|---|---|---|
| Registered → Silver | 100,000 | $3,310 | $0.14B |
| Silver → Gold | 200,000 | $6,620 | $0.28B |
| Gold → Platinum | 700,000 | $23,170 | $0.97B |
| Platinum → Diamond | 2,000,000 | $66,200 | $2.76B |
| Diamond → Vanguard | 4,000,000 | $132,400 | $5.52B |

And the stake is still theirs afterwards — this is payback on a *recoverable* asset, not a fee.

**Upgrade breakeven** — the monthly taker volume at which an upgrade's extra share repays the extra stake in a single month, versus spread over twelve:

| Upgrade | Extra USD staked | Share gain | Vol to repay in 1 month | Vol to repay in 12 months |
|---|---|---|---|---|
| Registered → Silver | $3,310 | +8% | $0.14B | $11M |
| Silver → Gold | $6,620 | +8% | $0.28B | $23M |
| Gold → Platinum | $23,170 | +8% | $0.97B | $80M |
| Platinum → Diamond | $66,200 | +8% | $2.76B | $230M |
| Diamond → Vanguard | $132,400 | +8% | $5.52B | $460M |

---

## 4. What the rate does not depend on

One dial, one input. The share is a pure function of ORDER staked and applies to every dollar of attributed revenue — the first dollar and the ten-millionth are paid at exactly the same percentage.

```
R = attributed Orderly base-fee revenue this period

payout = share(ORDER_staked) × R

no volume qualifier · no cap · no quota · no overflow · no decay
```

A distributor doing $50M/month and one doing $50B/month at the same stake earn the **same percentage**. The larger one earns more money because they generated more revenue, not because they unlocked a better rate. Volume moves the base, never the multiplier.

**The rate holds flat across three orders of magnitude:**

| Monthly taker volume | Orderly rev | Payout @ Registered | Payout @ Vanguard | Vanguard rate |
|---|---|---|---|---|
| $50M | $15,000 | $1,500 | $7,500 | 50.0% |
| $1B | $300,000 | $30,000 | $150,000 | 50.0% |
| $10B | $3,000,000 | $300,000 | $1,500,000 | 50.0% |
| $50B | $15,000,000 | $1,500,000 | $7,500,000 | 50.0% |

**The tradeoff this accepts.** A flat ladder saturates. At $0.0331/ORDER the whole ladder tops out at $231,700, so any distributor large enough to pass a BD application buys Vanguard once and never touches ORDER again — total staking demand is (number of distributors) × their tier, one time. That is a real limit, and it is the price of the rule that volume must never touch the rate. Demand grows by **recruiting more distributors and moving them up the ladder**, not by any single one scaling up. Section 8 sizes exactly what that is worth.

**Implementation details that matter:**

- **Staking above 7M buys nothing.** Vanguard is the ceiling; there is no reason to hold more than the top threshold.
- **Settlement is daily**, on that day's attributed revenue at that day's rate. No month-to-date accumulator and no true-up — there is nothing to accumulate against.
- **The daily stake snapshot uses the minimum stake held during that day**, so nobody can stake for one snapshot and unstake right after.
- **Crossing a threshold takes effect the next settlement day.** Upgrades apply forward only; no retroactive re-rating of revenue already paid.

---

## 5. Sponsorship — the closing tool, self-funded

Distributors can sponsor an invitee into better base pricing to win a deal. The **entire discount is debited from the distributor's payout**, which makes Orderly revenue-neutral:

$1B monthly taker volume, distributor at Vanguard (50%):

| Sponsored builder tier | Orderly actual rev | Discount debited | Distributor payout | **Orderly net** |
|---|---|---|---|---|
| Public (3.0 bps) | $300,000 | $0 | $150,000 | **$150,000** |
| Silver (2.75 bps) | $275,000 | $25,000 | $125,000 | **$150,000** |
| Gold (2.5 bps) | $250,000 | $50,000 | $100,000 | **$150,000** |
| Platinum (2.0 bps) | $200,000 | $100,000 | $50,000 | **$150,000** |
| Diamond (1.0 bps) | $100,000 | $200,000 | −$50,000 → floored to $0 | $100,000 |

Orderly nets exactly $150,000 in every permitted case. The distributor decides whether the discount wins a deal worth more than its cost — no approvals, no margin committee.

**The Diamond row is why sponsorship depth must be gated.** At 50% share a distributor earns 1.5 bps; sponsoring Diamond costs 2.0 bps. Unbounded, this goes negative and Orderly eats the difference. Authority table:

| Distributor tier | May sponsor invitee up to |
|---|---|
| Registered | — |
| Silver | Silver |
| Gold | Gold |
| Platinum | Gold |
| Diamond | Platinum |
| Vanguard | Platinum |

Hard rules: payout floors at $0 (never negative); if discount cost exceeds earned share two months running, the sponsorship auto-downgrades one tier with 30 days' notice. Diamond pricing stays a manual Orderly-side strategic assignment, never distributor-granted.

This gives a **second staking driver**: deeper discount authority is a closing weapon, and it is bought with ORDER.

---

## 6. Application, lifecycle, removal

**Application captures** (BD is assessing *can they deliver volume*): identity/entity + KYB, distribution channel and reach with evidence, named pipeline of ≥3 prospective builders, target segment, expected time-to-first-graduation, prior BD/partnership track record, conflicts (existing builder ownership, competing infra relationships).

**Decision:** BD approve / reject / conditional (approve with a 90-day first-graduation milestone). Target SLA 5 business days.

**On approval:** Registered tier, 10%, immediately live. No stake required to start — staking is the upgrade path, never the entry toll.

**Perpetual is unconditional.** No dormancy clause, no performance minimum. A distributor who lands one DEX and never works again keeps that payout for the life of the DEX.

**Termination for cause** (fraud, wash trading, misrepresentation, ToS breach): payouts stop, bindings revert to Orderly direct. This should be the only path that ever stops a payout.

---

## 7. Rules carried over and added

Binding rules: unidirectional binding (one distributor per invitee) · non-reciprocal (no A↔B) · binding at or before graduation · immutable once set · EOA registered as distributor cannot later convert to Builder Admin.

Added:
- **Daily accrual, daily settlement at 00:00 UTC.** Each day's payout uses that day's stake snapshot — no retroactive re-rating, no staking-for-one-day-then-unstaking.
- **Tier drops the moment an unstake request is submitted**, not when it completes. ORDER staking runs a **7-day unstaking period**; only one active request is allowed, a new request merges with the pending one and resets the full 7 days, and cancelling restakes the entire amount. If demotion waited for completion, a distributor would collect 7 days of top-tier payouts on tokens already on the way out — and the merge-and-reset behaviour would let them roll that indefinitely. Cancelling restores the tier at the next daily snapshot.
- **The 7-day exit is what makes the tier cost anything** — the stake is genuinely at risk through a drawdown.
- **Builder-owner distributors are permitted but must disclose.** Self-referral is economically pointless here (pay 3 bps, receive ≤50% back), so disclosure + monitoring is sufficient.
- **No traffic re-binding.** An existing builder's volume cannot be routed through a newly bound entity. The application's materially-new-entity test covers this.
- **Attribution is per-builder, perpetual, and survives distributor tier changes.**

---

## 8. Program cost to Orderly

Assumes $500M monthly taker volume per distributor, invitees on Public (3 bps). Realistic mix = 60% Registered / 20% Silver / 10% Gold / 6% Platinum / 3% Diamond / 1% Vanguard.

| Distributors | Gross Orderly rev/mo | All at 10% | All at 50% | **Blended, realistic mix** |
|---|---|---|---|---|
| 10 | $1,500,000 | $150,000 (10%) | $750,000 (50%) | **$214,000 (14%)** |
| 50 | $7,500,000 | $750,000 (10%) | $3,750,000 (50%) | **$1,070,000 (14%)** |
| 200 | $30,000,000 | $3,000,000 (10%) | $15,000,000 (50%) | **$4,280,000 (14%)** |

Blended cost lands ~14% of attributed revenue — and 100% of it is paid on **revenue that would not exist without the distributor**. Worst case is bounded at 50% by construction, and Orderly is indifferent to sponsorship, so there is no second leak.

**ORDER staking demand created:**

| Distributors | ORDER locked | USD @ $0.0331 | % of circulating |
|---|---|---|---|
| 10 | 2,700,000 | $89,370 | 0.66% |
| 50 | 13,500,000 | $446,850 | 3.30% |
| 200 | 54,000,000 | $1,787,400 | 13.19% |
| 500 | 135,000,000 | $4,468,500 | 32.97% |

Staking demand from this program is **bounded by distributor count**, not by their volume: 500 distributors at the realistic mix lock ~33% of circulating supply, and the same 500 lock no more than that no matter how large they grow. Growth in locked ORDER comes from recruiting more distributors and from more of them climbing the ladder.

---

## 9. Migration

1. Snapshot every existing binding and its trailing 90-day earnings under the old fee-spread model.
2. Auto-enroll every existing distributor at 10%, bindings preserved intact.
3. **90-day parity guarantee:** pay `max(old spread, new share)` per binding. Nobody is worse off during transition.
4. Publish each distributor's break-even stake — the ORDER needed for the new share to beat their old spread — at migration.
5. Day 91: new model only.
6. The application gate is not retroactive; everyone already bound is grandfathered as approved.

---

## 10. Decisions closed

| # | Question | Resolution |
|---|---|---|
| 1 | Does volume affect the rate? | **No.** The share is a pure function of ORDER staked. No volume qualifier, no capacity cap, no overflow, no decay (§3, §4) |
| 2 | Volume definition | **Billed taker notional** — single-sided by construction, taken from the fee engine, not analytics (§2) |
| 3 | ORDER price risk | **No re-pricing clause.** Thresholds are fixed ORDER amounts regardless of price |
| 4 | Unstake cooldown | **7 days**, confirmed in Orderly docs. Tier drops on request submission (§7) |
| 5 | Dormancy pause | **Removed.** Perpetual is unconditional; only termination for cause stops a payout (§6) |

**One consequence of #3 worth naming.** The ladder is ORDER-denominated, so if ORDER appreciates every tier costs more in dollars while buying the same rate. A 10× move makes Vanguard a $2.3M ask and the top of the ladder stops being reachable for mid-size partners. That pressure is good for the token and bad for recruitment, and it resolves in one of two ways when it bites: cut the ORDER thresholds, or accept that the ladder becomes a large-partner instrument and let the 10% floor carry everyone else. Worth deciding deliberately rather than by drift.

---

## Appendix — model

`model.py` in this directory regenerates every table. Edit `TIERS`, `ORDER_PRICE`, or the mix in `table_program_cost()` and re-run:

```
python3 model.py
```
