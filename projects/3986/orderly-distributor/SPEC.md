# Orderly Distributor Program v2 — Mechanics Spec

**Status:** draft for review · **Date:** 2026-09-01
**Reference price:** ORDER $0.0331 (CoinGecko, 2026-09-01) · mcap $13.5M · 409.5M circulating · FDV $33.1M

---

## 0. Decisions locked from your answers

| # | Decision |
|---|---|
| Gate | Application, approved by BD. Approval test = *can this applicant actually deliver volume* |
| Payout base | **Orderly's own base-fee revenue** from the recruited builder. Taker only (Orderly charges taker only) |
| Rate | 10% floor on approval → 50% ceiling |
| Tier driver | **ORDER staking only.** Volume buys status and privileges, never rate |
| Duration | Perpetual for the life of the recruited DEX |
| Migration | Force-migrate; only internal BDs are on v1 |
| Depth | Flat, one level. No sub-distributors |
| Target profile | Anyone with access to people who might launch a DEX or bolt perps onto an existing product (wallet apps, trading communities, agencies, regional partners) |

---

## 1. What actually changes

**v1 (today):** distributor earns the *fee spread* — `max(0.1 bps, invitee base taker fee − distributor base taker fee)`. Tier from `30d aggregate volume OR staking, higher wins`, where aggregate volume includes every invitee's volume.

**Three structural problems with v1:**

1. **The tier system is an anti-incentive to stake.** Distributor volume includes all invitee volume, so anyone who succeeds at the job hits Diamond on volume alone and never buys a single ORDER. The better you perform, the less reason you have to lock tokens. This is why v1 produces ~zero staking demand.
2. **The spread model pays distributors out of Orderly's margin in a way Orderly can't cap.** The spread is a function of two tier tables interacting, not a policy dial.
3. **Volume-driven tiers are gameable.** Wash volume promotes the distributor's own tier, which widens their spread.

**v2 fixes all three by separating the two axes:**

- **Cash (rate) ← staking only.** A clean policy dial, 10%–50%, that Orderly controls directly.
- **Status (privileges) ← volume.** Support, co-marketing, sponsorship authority, leads. No cash.

Secondary benefit: with rate decoupled from volume, **wash trading becomes strictly −EV.** A distributor who fakes volume causes the builder to pay 3 bps to Orderly and receives back at most 50% of it. There is no tier to farm. This removes an entire abuse class from v1.

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

| Tier | ORDER staked | USD @ $0.0331 | Share of Orderly rev | Monthly rev capacity | Payout at cap |
|---|---|---|---|---|---|
| Registered | 0 | $0 | 10% | n/a (floor rate) | — |
| Silver | 100,000 | $3,310 | 18% | $25,000 | $4,500/mo |
| Gold | 300,000 | $9,930 | 26% | $75,000 | $19,500/mo |
| Platinum | 1,000,000 | $33,100 | 34% | $250,000 | $85,000/mo |
| Diamond | 3,000,000 | $99,300 | 42% | $750,000 | $315,000/mo |
| Vanguard | 7,000,000 | $231,700 | 50% | $1,750,000 | $875,000/mo |

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

---

## 4. The capacity mechanic — this is the part that actually drives staking

**Problem with a plain ladder:** it saturates. At today's price the entire ladder tops out at $231,700. Any distributor serious enough to pass a BD application buys Vanguard on day one and never touches ORDER again. Total demand = (number of large distributors) × 7M, one time. That is not a flywheel, it's a toll booth.

**Fix:** each tier gives you a **rate** and a **quota of monthly revenue that rate applies to**.

```
capacity_usd_per_month = 0.25 × ORDER_staked

R = attributed Orderly revenue this month
payout = share × min(R, capacity)
       + share_one_tier_down × max(0, R − capacity)
```

Overflow drops exactly **one step** — never cascades further, never falls to the 10% floor. Registered has no capacity: 10% is unlimited, so nobody can ever earn less than 10% on anything.

**Worked, at Vanguard (7M ORDER → $1.75M capacity):**

| Monthly Orderly rev | Within capacity @ 50% | Overflow @ 42% | Payout | Effective rate |
|---|---|---|---|---|
| $1.00M ($3.3B vol) | $1.00M → $500,000 | — | $500,000 | 50.0% |
| $1.75M ($5.8B vol) | $1.75M → $875,000 | — | $875,000 | 50.0% |
| $3.00M ($10B vol) | $1.75M → $875,000 | $1.25M → $525,000 | $1,400,000 | 46.7% |
| $9.00M ($30B vol) | $1.75M → $875,000 | $7.25M → $3,045,000 | $3,920,000 | 43.6% |

The distributor at $10B/mo is leaving $100,000/month on the table. Closing it costs 5M more ORDER (~$165,000) — **payback under two months, and the stake is still theirs.** That is the whole design: the correct move is always "stake more," and how much you should stake is a function of how well you are doing. Staking demand grows with the program instead of stopping at 7M.

**Implementation details that matter:**

- **Stake above 7M keeps buying capacity** at 0.25 USD/ORDER at the 50% rate. No ceiling — that is the point.
- **Settlement stays daily, on a month-to-date accumulator.** Each day's revenue fills remaining capacity at the headline rate; the rest pays at the step-down. Resets at month start.
- **The daily stake snapshot uses the minimum stake held during that day**, so nobody can stake for one snapshot and unstake right after.

Scale check: at 3 bps, $1 of capacity ≈ $3,333 of monthly taker volume. Vanguard covers **$5.8B/month** fully at 50%.

| Portfolio monthly taker vol | Orderly rev | Flat ladder @ Vanguard | Capped @ Vanguard | Stake to uncap |
|---|---|---|---|---|
| $1B | $300,000 | $150,000 | $150,000 | 1,200,000 ORDER |
| $5B | $1,500,000 | $750,000 | $750,000 | 6,000,000 ORDER |
| $10B | $3,000,000 | $1,500,000 | $1,400,000 | 12,000,000 ORDER |
| $30B | $9,000,000 | $4,500,000 | $3,920,000 | 36,000,000 ORDER |

The cap does not bite at all below ~$5.8B/mo — small and mid distributors never feel it. It only engages for the handful of partners large enough that their staking decision moves the token, which is exactly where you want the pressure.

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

## 6. Performance ladder (volume → status, never cash)

Measured on 30d attributed taker volume across graduated invitees. Deliberately no rate attached.

| Level | Trigger | Unlocks |
|---|---|---|
| Registered | Approved | Dashboard, codes/links, self-serve collateral, Telegram support |
| Active | 1 graduated DEX | Named BD contact, deal-desk review, co-branded materials |
| Scaled | $250M/mo or 3 graduated DEXs | Inbound lead sharing, co-marketing, launch RT/QT, quarterly pipeline review |
| Strategic | $1B/mo or 8 graduated DEXs | Dedicated account manager, joint campaigns, PR & paid media, roadmap input |
| Flagship | $5B/mo or 20 graduated DEXs | Advisory board seat, event slots, first look at new products/chains, custom terms |

Everything here costs Orderly headcount and attention, not bps. It rewards the operators without touching the rate dial — and because it's the only thing volume buys, there's no reason to fake volume for it.

---

## 7. Application, lifecycle, removal

**Application captures** (BD is assessing *can they deliver volume*): identity/entity + KYB, distribution channel and reach with evidence, named pipeline of ≥3 prospective builders, target segment, expected time-to-first-graduation, prior BD/partnership track record, conflicts (existing builder ownership, competing infra relationships).

**Decision:** BD approve / reject / conditional (approve with a 90-day first-graduation milestone). Target SLA 5 business days.

**On approval:** Registered tier, 10%, immediately live. No stake required to start — staking is the upgrade path, never the entry toll.

**Perpetual is unconditional.** No dormancy clause, no performance minimum. A distributor who lands one DEX and never works again keeps that payout for the life of the DEX.

**Termination for cause** (fraud, wash trading, misrepresentation, ToS breach): payouts stop, bindings revert to Orderly direct. This should be the only path that ever stops a payout.

---

## 8. Rules carried over and added

Carried from v1: unidirectional binding (one distributor per invitee) · non-reciprocal (no A↔B) · binding at or before graduation · immutable once set · EOA registered as distributor cannot later convert to Builder Admin.

Added:
- **Daily accrual, daily settlement at 00:00 UTC.** Each day's payout uses that day's stake snapshot — no retroactive re-rating, no staking-for-one-day-then-unstaking.
- **Tier drops the moment an unstake request is submitted**, not when it completes. ORDER staking runs a **7-day unstaking period**; only one active request is allowed, a new request merges with the pending one and resets the full 7 days, and cancelling restakes the entire amount. If demotion waited for completion, a distributor would collect 7 days of top-tier payouts on tokens already on the way out — and the merge-and-reset behaviour would let them roll that indefinitely. Cancelling restores the tier at the next daily snapshot.
- **The 7-day exit is what makes the tier cost anything** — the stake is genuinely at risk through a drawdown.
- **Builder-owner distributors are permitted but must disclose.** Self-referral is economically pointless here (pay 3 bps, receive ≤50% back), so disclosure + monitoring is sufficient.
- **No traffic re-binding.** An existing builder's volume cannot be routed through a newly bound entity. The application's materially-new-entity test covers this.
- **Attribution is per-builder, perpetual, and survives distributor tier changes.**

---

## 9. Program cost to Orderly

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

Plus capacity-driven top-ups from any distributor above ~$7B/mo, which is the part that keeps growing.

---

## 10. Migration (internal BDs only)

1. Snapshot every existing binding and its trailing 90-day earnings under the v1 spread model.
2. Auto-enroll each internal BD as **Registered**, bindings preserved intact.
3. **90-day parity guarantee:** pay `max(v1 spread, v2 share)` per binding. Nobody is worse off during transition.
4. Publish each BD's break-even stake — the ORDER needed for v2 to beat their v1 spread — at migration.
5. Day 91: v2 only.
6. Application gate is **not** retroactive; existing internal BDs are grandfathered as approved.

---

## 11. Open decisions I need from you

1. **Capacity cap in v1, or flat ladder now and capacity in v2.1?** My recommendation is v1 — without it the program creates one-time staking demand and then stops. It only affects distributors above ~$7B/mo.
2. **Volume definition.** Is "taker volume" single-sided notional (the taker side of each match)? All my numbers assume yes. If your reported volume is two-sided, every payout figure halves.
3. **ORDER price risk.** Thresholds are ORDER-denominated, so a 10× token move makes Vanguard a $2.3M ask while capacity stays USD-denominated. Do you want an automatic review trigger (e.g. re-price thresholds if the 90-day TWAP moves >3×), or governance-by-hand?
4. **Unstake cooldown.** The public docs don't expose the staking contract's unbonding period. If there's a cooldown, tier demotion timing needs to match it — send me the mechanics and I'll write the clause.
5. **Is the 6-month dormancy pause acceptable** given "perpetual"? I've written it so existing payouts are never touched — only new bindings are blocked.

---

## Appendix — model

`model.py` in this directory regenerates every table. Edit `TIERS`, `ORDER_PRICE`, or the mix in `table_program_cost()` and re-run:

```
python3 model.py
```
