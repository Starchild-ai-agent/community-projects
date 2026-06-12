#!/usr/bin/env python3
"""Shadow logger — collect a live tape + dry-run quotes for ANY target asset.

This is the component that earns a trustworthy (>=75) score: it records a long,
multi-day trade tape against the quotes the strategy WOULD post — no orders, no
capital. Feed its output back into quotesim.tape_validate for a real number.

Per cycle (default 10s):
  1. fetch oracle (public futures mark/index) + recent trade tape for SYMBOL
  2. run the dry-mode quote engine -> the ladder we'd rest right now
  3. apply the crossing model to new tape prints -> predicted fills
  4. append a telemetry row + any predicted fills to jsonl

Data source: Orderly public endpoints for a listed PERP symbol, OR a CEX via
CoinGlass price/trades. Configurable. Read-only; safe to run under the watchdog.

Usage:
  SYMBOL=PERP_VVV_USDC_xxx python3 shadow_logger.py --cycles 1   # smoke test
  (deploy via scheduled_task watchdog for continuous multi-day collection)
"""
import os, sys, json, time, argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from quotesim.config import AssetConfig, StrategyConfig
from quotesim.engine import Engine, State

OUTDIR = HERE / "shadow"
OUTDIR.mkdir(exist_ok=True)


ORDERLY_BASE = os.environ.get("ORDERLY_BASE", "https://api.orderly.org")


def _orderly_public(path):
    from httpcompat import http_get
    return http_get(f"{ORDERLY_BASE}{path}", timeout=10).json()


def fetch_oracle_and_tape(symbol, since_t):
    """Return (mid, [new prints since since_t]) from Orderly public endpoints."""
    fut = _orderly_public(f"/v1/public/futures/{symbol}").get("data", {})
    mid = float(fut.get("index_price") or fut.get("mark_price") or 0)
    tr = _orderly_public(f"/v1/public/market_trades?symbol={symbol}&limit=100")
    rows = tr.get("data", {}).get("rows", [])
    prints = [{"t": r["executed_timestamp"] / 1000.0, "price": float(r["executed_price"]),
               "qty": float(r["executed_quantity"]), "aggressor": r["side"]}
              for r in rows if r["executed_timestamp"] / 1000.0 > since_t]
    prints.sort(key=lambda x: x["t"])
    return mid, prints


def crossing_fills(prints, quotes, mid, tol_bps=2.0):
    """quotes: list of (side, price, lot_qty). Returns predicted fills."""
    out = []
    bids = sorted([q for q in quotes if q[0] == "BUY"], key=lambda x: -x[1])
    asks = sorted([q for q in quotes if q[0] == "SELL"], key=lambda x: x[1])
    tol = mid * tol_bps / 10000.0
    for p in prints:
        if p["aggressor"] == "SELL":          # hits our bids -> we BUY
            for _, price, lot in bids:
                if price + tol >= p["price"]:
                    out.append({"t": p["t"], "side": "BUY", "price": price,
                                "qty": min(p["qty"], lot), "oracle": mid})
                    break
        else:                                  # BUY aggressor -> we SELL
            for _, price, lot in asks:
                if price - tol <= p["price"]:
                    out.append({"t": p["t"], "side": "SELL", "price": price,
                                "qty": min(p["qty"], lot), "oracle": mid})
                    break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default=os.environ.get("SYMBOL", "PERP_NATGAS_USDC_arthur"))
    ap.add_argument("--cycles", type=int, default=0, help="0 = run forever")
    ap.add_argument("--interval", type=float, default=10.0)
    ap.add_argument("--side-notional", type=float, default=30000.0)
    args = ap.parse_args()

    asset = AssetConfig(symbol=args.symbol)
    strat = StrategyConfig(side_notional_usd=args.side_notional)
    eng = Engine(asset, strat)
    st = State()

    tel_f = open(OUTDIR / f"{args.symbol}_shadow.jsonl", "a")
    fill_f = open(OUTDIR / f"{args.symbol}_fills.jsonl", "a")
    last_t = time.time() - 60
    n = 0
    print(f"shadow logger: {args.symbol}  side=${args.side_notional:.0f}  "
          f"interval={args.interval}s  cycles={'∞' if args.cycles == 0 else args.cycles}")
    while True:
        try:
            mid, prints = fetch_oracle_and_tape(args.symbol, last_t)
            if mid > 0:
                quotes = eng._quotes(mid, st)
                fills = crossing_fills(prints, quotes, mid)
                for f in fills:
                    # update shadow inventory via engine accounting
                    from quotesim.fillmodels import Fill
                    eng._apply(Fill(f["side"], f["price"], f["qty"], f["oracle"]), st)
                    fill_f.write(json.dumps(f) + "\n")
                if prints:
                    last_t = max(p["t"] for p in prints)
                row = {"ts": time.time(), "mid": mid, "n_quotes": len(quotes),
                       "inv": round(st.inv, 1), "inv_usd": round(st.inv * mid),
                       "spread_pnl": round(st.spread_pnl, 2),
                       "directional_pnl": round(st.directional_pnl, 2),
                       "new_prints": len(prints), "new_fills": len(fills)}
                tel_f.write(json.dumps(row) + "\n"); tel_f.flush(); fill_f.flush()
                if n % 6 == 0:
                    print(f"  [{time.strftime('%H:%M:%S')}] mid={mid:.4f} "
                          f"inv={st.inv:+.0f} prints+{len(prints)} fills+{len(fills)}")
        except Exception as e:
            print(f"  cycle err: {e}", file=sys.stderr)
        n += 1
        if args.cycles and n >= args.cycles:
            break
        time.sleep(args.interval)
    print(f"done {n} cycles -> {OUTDIR}")


if __name__ == "__main__":
    main()
