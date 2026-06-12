#!/usr/bin/env python3
"""Phase 2 — paper-live on Orderly. Zero keys, zero custody.

Points the SAME dry-run quote engine the simulator uses at Orderly's LIVE public
feeds (mark price + trade tape) and tracks what the strategy WOULD do in real
time: which resting quotes the real prints would have crossed, how inventory
builds, and the running spread / directional PnL split. No orders, no API keys,
no money — it only reads public endpoints.

This is the bridge between "evaluate on history" and "go live": the user watches
their exact config trade live data before any capital is involved.

Cycle model (driven by scheduled_task every ~1 min; state persists between runs):
  --collect   one cycle per symbol: fetch mark + new tape prints, rebuild the
              dry-run ladder, predict crossings, update + persist inventory.
  --status    read the running session(s) and print a JSON snapshot for the UI.

Public endpoints (no auth):
  GET /v1/public/futures/{symbol}              -> mark_price (the oracle)
  GET /v1/public/market_trades?symbol=&limit=  -> recent taker prints (the tape)

Smoke test:
  python3 paperlive_orderly.py --collect --symbols PERP_ETH_USDC,PERP_BTC_USDC
  python3 paperlive_orderly.py --status  --symbols PERP_ETH_USDC,PERP_BTC_USDC
"""
import os, sys, json, time, argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from quotesim.config import AssetConfig, StrategyConfig
from quotesim.engine import Engine, State
from quotesim.fillmodels import Fill

OUT = HERE / "paper"; OUT.mkdir(exist_ok=True)
BASE = "https://api.orderly.org"


def _get(path):
    from httpcompat import http_get
    return http_get(BASE + path, timeout=20).json()


def _mark(symbol):
    d = _get(f"/v1/public/futures/{symbol}")
    dd = d.get("data", {}) if isinstance(d, dict) else {}
    return float(dd.get("mark_price") or dd.get("index_price") or 0)


def _tape(symbol, limit=100):
    d = _get(f"/v1/public/market_trades?symbol={symbol}&limit={limit}")
    rows = d.get("data", {}).get("rows", []) if isinstance(d, dict) else []
    # normalize + sort oldest->newest
    out = [{"ts": int(r["executed_timestamp"]), "px": float(r["executed_price"]),
            "sz": float(r["executed_quantity"]), "side": r["side"]} for r in rows]
    out.sort(key=lambda x: x["ts"])
    return out


def _paths(symbol):
    s = symbol.replace("/", "_")
    return (OUT / f"OD_{s}_state.json", OUT / f"OD_{s}_shadow.jsonl",
            OUT / f"OD_{s}_fills.jsonl", OUT / f"OD_{s}_cfg.json")


def _load_state(symbol):
    sp, _, _, _ = _paths(symbol)
    if sp.exists():
        d = json.load(open(sp))
        st = State()
        for k, v in d.items():
            if hasattr(st, k):
                setattr(st, k, v)
        return st, d.get("last_ts", 0), d.get("started_ts", time.time())
    return State(), 0, time.time()


def _save_state(symbol, st, last_ts, started_ts):
    sp, _, _, _ = _paths(symbol)
    d = {k: getattr(st, k) for k in
         ("inv", "avg", "realized", "spread_pnl", "directional_pnl",
          "fees", "n_fills", "gross_vol", "peak_inv_usd")}
    d.update(last_ts=last_ts, started_ts=started_ts)
    json.dump(d, open(sp, "w"))


def _load_cfg(symbol):
    _, _, _, cp = _paths(symbol)
    if cp.exists():
        return json.load(open(cp))
    return {"side_notional_usd": 30000}


def save_cfg(symbol, side_notional, strat_dict):
    _, _, _, cp = _paths(symbol)
    cfg = {**(strat_dict or {}), "side_notional_usd": side_notional}
    json.dump(cfg, open(cp, "w"))


def set_active(symbol, on):
    _, _, _, cp = _paths(symbol)
    cfg = json.load(open(cp)) if cp.exists() else {"side_notional_usd": 30000}
    cfg["active"] = bool(on)
    json.dump(cfg, open(cp, "w"))


def reset_session(symbol):
    """Wipe state + history so a fresh session starts flat at next collect."""
    sp, shadow_p, fills_p, _ = _paths(symbol)
    for p in (sp, shadow_p, fills_p):
        if p.exists():
            p.unlink()


def list_active():
    out = []
    for cp in OUT.glob("OD_*_cfg.json"):
        try:
            cfg = json.load(open(cp))
            if cfg.get("active"):
                sym = cp.name[3:-9]  # strip "OD_" prefix and "_cfg.json"
                out.append(sym)
        except Exception:
            pass
    return out


def crossing_fills(prints, quotes, mark, tol_bps=2.0):
    """Orderly market_trades `side` = taker/aggressor side.
    side SELL = aggressor sold into our BID  -> we BUY.
    side BUY  = aggressor lifted our ASK     -> we SELL."""
    bids = sorted([q for q in quotes if q[0] == "BUY"], key=lambda x: -x[1])
    asks = sorted([q for q in quotes if q[0] == "SELL"], key=lambda x: x[1])
    tol = mark * tol_bps / 10000.0
    out = []
    for p in prints:
        px, sz = p["px"], p["sz"]
        if p["side"] == "SELL":                    # hits our bid -> we buy
            for _, price, lot in bids:
                if price + tol >= px:
                    out.append(Fill("BUY", price, min(sz, lot), mark)); break
        else:                                       # lifts our ask -> we sell
            for _, price, lot in asks:
                if price - tol <= px:
                    out.append(Fill("SELL", price, min(sz, lot), mark)); break
    return out


def collect_one(symbol):
    st, last_ts, started = _load_state(symbol)
    cfg = _load_cfg(symbol)
    mark = _mark(symbol)
    if mark <= 0:
        return {"symbol": symbol, "ok": False, "error": "no mark"}
    tape = _tape(symbol)

    # baseline cycle: first run has no prior timestamp. Don't retroactively fill
    # against the backlog — start flat and only count prints from now forward.
    if last_ts == 0:
        last_ts = max((t["ts"] for t in tape), default=int(time.time() * 1000))
        _save_state(symbol, st, last_ts, started)
        return {"symbol": symbol, "ok": True, "baseline": True, "mark": mark,
                "new_prints": 0, "new_fills": 0, "n_fills": 0}

    prints = [t for t in tape if t["ts"] > last_ts]

    strat = StrategyConfig.from_dict(cfg)
    eng = Engine(AssetConfig(symbol=symbol), strat)
    # Re-quote per print (not once per cycle): a live MM continuously re-quotes,
    # so inventory skew/suppression re-evaluates as inventory builds and caps it.
    # Quote around the oracle `mark` (sticky); prints move around it and cross.
    fills = []
    for p in prints:
        q = eng._quotes(mark, st)
        for f in crossing_fills([p], q, mark):
            eng._apply(f, st)
            fills.append(f)
            st.peak_inv_usd = max(st.peak_inv_usd, abs(st.inv * mark))
    st.directional_pnl = round(st.realized + st.inv * (mark - st.avg), 4)
    st.peak_inv_usd = max(st.peak_inv_usd, abs(st.inv * mark))
    if prints:
        last_ts = max(p["ts"] for p in prints)

    _, shadow_p, fills_p, _ = _paths(symbol)
    if fills:
        with open(fills_p, "a") as ff:
            for f in fills:
                ff.write(json.dumps({"t": time.time(), "side": f.side,
                                     "price": f.price, "qty": f.qty, "mark": mark}) + "\n")
    row = {"ts": time.time(), "mark": mark, "inv": round(st.inv, 4),
           "inv_usd": round(st.inv * mark, 2),
           "spread_pnl": round(st.spread_pnl, 2),
           "directional_pnl": round(st.directional_pnl, 2),
           "total_pnl": round(st.spread_pnl + st.directional_pnl, 2),
           "new_prints": len(prints), "new_fills": len(fills),
           "n_fills": st.n_fills}
    with open(shadow_p, "a") as sf:
        sf.write(json.dumps(row) + "\n")
    _save_state(symbol, st, last_ts, started)
    return {"symbol": symbol, "ok": True, "elapsed_min": round((time.time() - started) / 60, 1), **row}


def status_one(symbol):
    st, last_ts, started = _load_state(symbol)
    _, shadow_p, _, _ = _paths(symbol)
    mins = max((time.time() - started) / 60.0, 1e-6)
    days = mins / 1440.0
    spark = []
    if shadow_p.exists():
        rows = [json.loads(l) for l in open(shadow_p) if l.strip()]
        spark = [[r["ts"], r.get("inv_usd", 0), r.get("total_pnl", 0)] for r in rows[-240:]]
    total = st.spread_pnl + st.directional_pnl
    return {
        "symbol": symbol, "cfg": _load_cfg(symbol),
        "running_min": round(mins, 1), "running_days": round(days, 3),
        "n_fills": st.n_fills, "fills_per_day": round(st.n_fills / max(days, 1e-6), 1),
        "inv_usd": round(st.inv * (st.avg or 0), 2) if st.inv else 0.0,
        "inv_lots": round(st.inv, 4),
        "spread_pnl": round(st.spread_pnl, 2),
        "directional_pnl": round(st.directional_pnl, 2),
        "total_pnl": round(total, 2),
        "peak_inv_usd": round(st.peak_inv_usd, 2),
        "spread_per_day": round(st.spread_pnl / max(days, 1e-6), 2),
        "directional_per_day": round(st.directional_pnl / max(days, 1e-6), 2),
        "total_per_day": round(total / max(days, 1e-6), 2),
        "spark": spark,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--symbols", default=os.environ.get("PL_SYMBOLS", "PERP_ETH_USDC"))
    ap.add_argument("--side-notional", type=float,
                    default=float(os.environ.get("PL_SIDE", "30000")))
    ap.add_argument("--strat", default=os.environ.get("PL_STRAT", ""))
    ap.add_argument("--save-cfg", action="store_true",
                    help="persist the config for these symbols (call once at session start)")
    args = ap.parse_args()
    syms = [s.strip() for s in args.symbols.split(",") if s.strip()]
    strat = json.loads(args.strat) if args.strat else {}

    if args.save_cfg:
        for s in syms:
            save_cfg(s, args.side_notional, strat)
        print(json.dumps({"ok": True, "saved": syms})); return
    if args.status:
        print(json.dumps({"ok": True, "sessions": [status_one(s) for s in syms]})); return
    # default: collect
    out = [collect_one(s) for s in syms]
    # print only a compact line (task system pushes non-empty stdout; keep quiet-ish)
    actionable = [o for o in out if o.get("new_fills")]
    print(json.dumps({"ok": True, "cycles": out}) if actionable else "", end="")


if __name__ == "__main__":
    main()
