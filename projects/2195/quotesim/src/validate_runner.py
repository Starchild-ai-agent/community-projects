#!/usr/bin/env python3
"""Real-tape validation runner — the trustworthy path, with zero CLI for the user.

The OHLC simulator overcounts fills (no queue position), so it self-reports a low
trust score. This runner earns a real number by recording the LIVE trade tape of
a reference venue against the quotes the strategy WOULD rest — no orders, no
capital — then scoring the accumulated sample.

Two modes (an agent drives both via scheduled_task; the user never types here):

  --collect   one cycle: fetch oracle mark + recent trades for a Hyperliquid
              coin, build the dry-run ladder, predict crossings, append tape +
              fills, persist inventory across cycles. Run every few minutes.

  --score     read everything collected so far, compute per-day spread /
              directional / fills, and a readiness verdict. Prints JSON.

Reference venue: Hyperliquid public endpoints (every listed perp has an oracle
AND a public trade tape). RWA/Pyth assets are oracle-only (no tape) → not
validatable here; the tool keeps them at risk-shape-only by design.

Usage (smoke test):
  python3 validate_runner.py --collect --coin HYPE
  python3 validate_runner.py --score   --coin HYPE
"""
import os, sys, json, time, argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from quotesim.config import AssetConfig, StrategyConfig
from quotesim.engine import Engine, State
from quotesim.fillmodels import Fill

OUT = HERE / "shadow"; OUT.mkdir(exist_ok=True)
HL_INFO = "https://api.hyperliquid.xyz/info"

# readiness thresholds — below these, dollars are still too noisy to trust
MIN_FILLS = 200
MIN_DAYS = 2.0


def _post(body):
    from httpcompat import http_post
    return http_post(HL_INFO, json=body, timeout=15).json()


def _mark(coin):
    """Current oracle/mark for a HL coin. Handles xyz:NATGAS-style DEX coins."""
    # DEX coins (xyz:*) live on a separate meta endpoint
    if coin.startswith("xyz:"):
        try:
            meta, ctxs = _post({"type": "metaAndAssetCtxs", "dex": "xyz"})
            for u, c in zip(meta["universe"], ctxs):
                if u["name"] == coin:
                    return float(c.get("oraclePx") or c.get("markPx") or 0)
        except Exception:
            pass
        return 0.0
    meta, ctxs = _post({"type": "metaAndAssetCtxs"})
    for u, c in zip(meta["universe"], ctxs):
        if u["name"] == coin:
            return float(c.get("oraclePx") or c.get("markPx") or 0)
    return 0.0


def _recent_trades(coin):
    d = _post({"type": "recentTrades", "coin": coin})
    return d if isinstance(d, list) else []


def _fsafe(coin):
    return coin.replace(":", "_")


def _state_path(coin):
    return OUT / f"HL_{_fsafe(coin)}_state.json"


def _load_state(coin):
    p = _state_path(coin)
    if p.exists():
        d = json.load(open(p))
        st = State()
        for k, v in d.items():
            if hasattr(st, k):
                setattr(st, k, v)
        return st, d.get("last_tid", 0), d.get("started_ts", time.time())
    return State(), 0, time.time()


def _save_state(coin, st, last_tid, started_ts):
    d = {k: getattr(st, k) for k in
         ("inv", "avg", "realized", "spread_pnl", "directional_pnl",
          "fees", "n_fills", "gross_vol", "peak_inv_usd")}
    d.update(last_tid=last_tid, started_ts=started_ts)
    json.dump(d, open(_state_path(coin), "w"))


def crossing_fills(prints, quotes, mark, tol_bps=2.0):
    """prints: HL trades. side 'A' = sell aggressor (hits our bids -> we BUY),
    side 'B' = buy aggressor (lifts our asks -> we SELL)."""
    bids = sorted([q for q in quotes if q[0] == "BUY"], key=lambda x: -x[1])
    asks = sorted([q for q in quotes if q[0] == "SELL"], key=lambda x: x[1])
    tol = mark * tol_bps / 10000.0
    out = []
    for p in prints:
        px = float(p["px"]); sz = float(p["sz"])
        if p["side"] == "A":                       # aggressor sold -> we buy
            for _, price, lot in bids:
                if price + tol >= px:
                    out.append(Fill("BUY", price, min(sz, lot), mark)); break
        else:                                       # aggressor bought -> we sell
            for _, price, lot in asks:
                if price - tol <= px:
                    out.append(Fill("SELL", price, min(sz, lot), mark)); break
    return out


def collect(coin, side_notional, strat_dict):
    st, last_tid, started = _load_state(coin)
    mark = _mark(coin)
    if mark <= 0:
        out = {"ok": False, "error": f"no mark for {coin}"}
        print(json.dumps(out)); return out
    trades = _recent_trades(coin)
    fresh = [t for t in trades if t.get("tid", 0) > last_tid]
    fresh.sort(key=lambda t: t["tid"])

    strat = StrategyConfig.from_dict({**(strat_dict or {}),
                                      "side_notional_usd": side_notional})
    eng = Engine(AssetConfig(symbol=f"PERP_{coin}_USDC"), strat)
    quotes = eng._quotes(mark, st)
    fills = crossing_fills(fresh, quotes, mark)
    for f in fills:
        eng._apply(f, st)
    # directional = realized closes + open inventory mark-to-market
    st.directional_pnl = round(st.realized + st.inv * (mark - st.avg), 4)
    st.peak_inv_usd = max(st.peak_inv_usd, abs(st.inv * mark))
    if fresh:
        last_tid = max(t["tid"] for t in fresh)

    fill_f = open(OUT / f"HL_{_fsafe(coin)}_fills.jsonl", "a")
    for f in fills:
        fill_f.write(json.dumps({"t": time.time(), "side": f.side,
                                 "price": f.price, "qty": f.qty, "mark": mark}) + "\n")
    fill_f.close()
    tel = {"ts": time.time(), "mark": mark, "n_quotes": len(quotes),
           "inv": round(st.inv, 2), "inv_usd": round(st.inv * mark),
           "spread_pnl": round(st.spread_pnl, 2),
           "directional_pnl": round(st.directional_pnl, 2),
           "new_prints": len(fresh), "new_fills": len(fills),
           "n_fills": st.n_fills}
    with open(OUT / f"HL_{_fsafe(coin)}_shadow.jsonl", "a") as tf:
        tf.write(json.dumps(tel) + "\n")
    _save_state(coin, st, last_tid, started)
    out = {"ok": True, "coin": coin, **tel,
           "elapsed_days": round((time.time() - started) / 86400, 3)}
    print(json.dumps(out))
    return out


def score(coin):
    sp = OUT / f"HL_{_fsafe(coin)}_shadow.jsonl"
    st, last_tid, started = _load_state(coin)
    if not sp.exists() or st.n_fills == 0:
        out = {"ok": True, "ready": False, "confidence": 0, "days": 0.0,
               "fills": st.n_fills,
               "verdict": "COLLECTING — no fills yet; collection just started"}
        print(json.dumps(out)); return out
    days = max((time.time() - started) / 86400, 1e-6)
    spread_d = st.spread_pnl / days
    dir_d = st.directional_pnl / days
    fills_d = st.n_fills / days
    ready = st.n_fills >= MIN_FILLS and days >= MIN_DAYS
    # a simple, honest confidence: how far through the sample budget we are
    conf = min(100, round(min(st.n_fills / MIN_FILLS, days / MIN_DAYS) * 100))
    out = {"ok": True, "coin": coin, "ready": ready, "confidence": conf,
           "days": round(days, 2), "fills": st.n_fills,
           "peak_inv_usd": round(st.peak_inv_usd)}
    if ready:
        out["verdict"] = "READY — real-tape sample is large enough to trust the dollars"
        out.update(fills_per_day=round(fills_d, 1),
                   spread_per_day=round(spread_d, 2),
                   directional_per_day=round(dir_d, 2),
                   total_per_day=round(spread_d + dir_d, 2))
    else:
        # dollars are still too noisy on a tiny window — withhold them on purpose
        out["verdict"] = (f"COLLECTING — {st.n_fills}/{MIN_FILLS} fills, "
                          f"{days:.1f}/{MIN_DAYS} days. Dollars hidden until the "
                          f"sample is large enough to mean something.")
    print(json.dumps(out))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--coin", default=os.environ.get("VAL_COIN", "HYPE"))
    ap.add_argument("--side-notional", type=float,
                    default=float(os.environ.get("VAL_SIDE", "30000")))
    ap.add_argument("--strat", default=os.environ.get("VAL_STRAT", ""))
    args = ap.parse_args()
    strat = json.loads(args.strat) if args.strat else {}
    if args.score:
        score(args.coin)
    else:
        collect(args.coin, args.side_notional, strat)


if __name__ == "__main__":
    main()
