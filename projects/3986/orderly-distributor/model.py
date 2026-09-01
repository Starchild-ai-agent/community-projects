#!/usr/bin/env python3
"""Orderly Distributor Program v2 — economics model.

Payout base = Orderly's own base-taker-fee revenue from a bound builder.
Distributor share % is set by ORDER staking tier ONLY.

Volume is NOT a qualifier and NOT a rate modifier. Volume only determines how
much revenue exists to split; the percentage of that revenue is a pure function
of ORDER staked. There is no cap, no quota, no overflow, no decay.
"""

ORDER_PRICE = 0.0331  # USD, CoinGecko 2026-09-01

# Orderly base taker fee by BUILDER tier (bps) — from Builder Staking Programme
BUILDER_RATE = {"Public": 3.00, "Silver": 2.75, "Gold": 2.50, "Platinum": 2.00, "Diamond": 1.00}

# Distributor ladder: stake (ORDER) -> share of Orderly revenue.
# 10% floor on approval, 50% ceiling at the top of the ladder.
TIERS = [
    ("Registered", 0,         0.10),
    ("Silver",     100_000,   0.18),
    ("Gold",       300_000,   0.26),
    ("Platinum",   1_000_000, 0.34),
    ("Diamond",    3_000_000, 0.42),
    ("Vanguard",   7_000_000, 0.50),
]


def orderly_rev(volume_usd, builder_tier="Public"):
    """Orderly's base-fee revenue on taker volume."""
    return volume_usd * BUILDER_RATE[builder_tier] / 10_000


def payout(monthly_rev, tier_idx):
    """Flat share of attributed revenue. The rate never varies with volume."""
    return monthly_rev * TIERS[tier_idx][2]


def table_ladder():
    rows = ["| Tier | ORDER staked | USD @ $0.0331 | Share of Orderly rev |",
            "|---|---|---|---|"]
    for name, stake, share in TIERS:
        rows.append(f"| {name} | {stake:,} | ${stake*ORDER_PRICE:,.0f} | {share:.0%} |")
    return "\n".join(rows)


def table_upgrade_roi():
    """Incremental stake vs incremental earnings — payback in monthly TAKER volume."""
    rows = ["| Upgrade | Extra ORDER | Extra USD staked | Share gain | Extra $ per $100M taker vol | Cumulative taker vol to repay stake |",
            "|---|---|---|---|---|---|"]
    for i in range(1, len(TIERS)):
        pname, pstake, pshare = TIERS[i-1]
        name, stake, share = TIERS[i]
        d_stake = stake - pstake
        d_usd = d_stake * ORDER_PRICE
        d_share = share - pshare
        per_100m = orderly_rev(100e6) * d_share
        repay_vol = d_usd / (orderly_rev(1) * d_share) if d_share else 0
        rows.append(f"| {pname} → {name} | {d_stake:,} | ${d_usd:,.0f} | +{d_share:.0%} | ${per_100m:,.0f} | ${repay_vol/1e9:,.2f}B |")
    return "\n".join(rows)


def table_portfolio(volumes=(50e6, 250e6, 1e9, 5e9, 20e9)):
    """What a distributor earns at each tier for a given monthly portfolio taker volume."""
    rows = ["| Monthly taker vol (portfolio) | Orderly rev | " + " | ".join(t[0] for t in TIERS) + " |",
            "|---" * (len(TIERS) + 2) + "|"]
    for v in volumes:
        rev = orderly_rev(v)
        cells = " | ".join(f"${payout(rev, i):,.0f}" for i in range(len(TIERS)))
        rows.append(f"| ${v/1e6:,.0f}M | ${rev:,.0f} | {cells} |")
    return "\n".join(rows)


def table_breakeven():
    """Monthly taker volume at which each upgrade's share gain covers the stake
    outlay in ONE month, and in twelve."""
    rows = ["| Upgrade | Extra USD staked | Share gain | Vol to repay in 1 month | Vol to repay in 12 months |",
            "|---|---|---|---|---|"]
    for i in range(1, len(TIERS)):
        pname, pstake, pshare = TIERS[i-1]
        name, stake, share = TIERS[i]
        d_usd = (stake - pstake) * ORDER_PRICE
        d_share = share - pshare
        per_dollar = orderly_rev(1) * d_share
        v1 = d_usd / per_dollar
        rows.append(f"| {pname} → {name} | ${d_usd:,.0f} | +{d_share:.0%} | ${v1/1e9:,.2f}B | ${v1/12/1e6:,.0f}M |")
    return "\n".join(rows)


def table_sponsorship():
    """Distributor sponsors an invitee into cheaper pricing; cost is debited from
    the distributor's share so Orderly is INDIFFERENT."""
    vol = 1e9
    notional = orderly_rev(vol, "Public")
    rows = [f"Worked on $1B monthly taker volume, distributor at Vanguard (50%).\n",
            "| Sponsored builder tier | Orderly actual rev | Discount cost (debited) | Distributor payout | Orderly net |",
            "|---|---|---|---|---|"]
    for bt in ["Public", "Silver", "Gold", "Platinum", "Diamond"]:
        actual = orderly_rev(vol, bt)
        discount = notional - actual
        pay = max(0.0, notional * 0.50 - discount)
        rows.append(f"| {bt} ({BUILDER_RATE[bt]} bps) | ${actual:,.0f} | ${discount:,.0f} | ${pay:,.0f} | ${actual-pay:,.0f} |")
    return "\n".join(rows)


def table_program_cost(n_dists=(10, 50, 200), vol_each=500e6):
    rows = [f"Assumes every distributor runs ${vol_each/1e6:,.0f}M monthly taker volume, all invitees on Public (3 bps).\n",
            "| Distributors | Gross Orderly rev/mo | If all Registered (10%) | If all Vanguard (50%) | Blended @ realistic mix |",
            "|---|---|---|---|---|"]
    mix = [0.60, 0.20, 0.10, 0.06, 0.03, 0.01]
    for n in n_dists:
        rev_each = orderly_rev(vol_each)
        gross = rev_each * n
        lo = n * payout(rev_each, 0)
        hi = n * payout(rev_each, 5)
        blended = sum(n * w * payout(rev_each, i) for i, w in enumerate(mix))
        rows.append(f"| {n} | ${gross:,.0f} | ${lo:,.0f} ({lo/gross:.0%}) | ${hi:,.0f} ({hi/gross:.0%}) | ${blended:,.0f} ({blended/gross:.0%}) |")
    return "\n".join(rows)


def table_staking_demand():
    """ORDER locked if the program hits N distributors at a given mix."""
    mix = [0.60, 0.20, 0.10, 0.06, 0.03, 0.01]
    rows = ["| Distributors | ORDER locked | USD @ $0.0331 | % of circulating (409.5M) |", "|---|---|---|---|"]
    for n in (10, 50, 200, 500):
        locked = sum(n * w * TIERS[i][1] for i, w in enumerate(mix))
        rows.append(f"| {n} | {locked:,.0f} | ${locked*ORDER_PRICE:,.0f} | {locked/409_464_543*100:.2f}% |")
    return "\n".join(rows)


if __name__ == "__main__":
    print("## A. Distributor stake ladder\n");          print(table_ladder())
    print("\n## B. Upgrade ROI\n");                      print(table_upgrade_roi())
    print("\n## C. Payout by portfolio size\n");         print(table_portfolio())
    print("\n## D. Upgrade breakeven volume\n");         print(table_breakeven())
    print("\n## E. Sponsorship cost internalisation\n"); print(table_sponsorship())
    print("\n## F. Program cost to Orderly\n");          print(table_program_cost())
    print("\n## G. ORDER staking demand created\n");     print(table_staking_demand())
