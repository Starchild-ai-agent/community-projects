#!/usr/bin/env python3
"""QuoteSim dashboard backend (Flask).

GET  /                  -> dashboard.html
GET  /api/exchanges     -> CoinGlass-supported exchanges (for the asset picker)
POST /api/fetch         -> pull 5m OHLC for ANY exchange+symbol, cache as a target
POST /api/run           -> run engine on a target (builtin or fetched) under a
                           config, calibrated + trust-scored on NATGAS truth.
GET  /api/tape          -> the real NATGAS tape-replay validation result.
GET  /api/assets        -> available targets (builtin + fetched this session).
"""
import json, os, sys, math, time, threading
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# Optional: CoinGlass skill (Starchild) enables the any-exchange fetch path.
_CG = os.environ.get("COINGLASS_SKILL_DIR", "/data/workspace/skills/coinglass")
if Path(_CG).exists():
    sys.path.insert(0, _CG)
from quotesim import (AssetConfig, StrategyConfig, Engine, OHLCTouchFill,
                      realized_vol_annual, calibrate, trust_score)
import paperlive_orderly as pl

# ---- Hyperliquid: the oracle-backed asset universe + candle source ----
HL_INFO = "https://api.hyperliquid.xyz/info"
_HL_UNIVERSE = {"ts": 0, "assets": []}


def _hl_universe():
    """Cached list of HL perps (each has an oracle price). Refresh hourly."""
    if time.time() - _HL_UNIVERSE["ts"] < 3600 and _HL_UNIVERSE["assets"]:
        return _HL_UNIVERSE["assets"]
    from httpcompat import http_post
    r = http_post(HL_INFO, json={"type": "metaAndAssetCtxs"}, timeout=15)
    meta, ctxs = r.json()
    assets = []
    for u, c in zip(meta["universe"], ctxs):
        if u.get("isDelisted"):
            continue
        ox = c.get("oraclePx")
        assets.append({"name": u["name"], "oracle": float(ox) if ox else None,
                       "max_lev": u.get("maxLeverage")})
    assets.sort(key=lambda a: a["name"])
    _HL_UNIVERSE.update(ts=time.time(), assets=assets)
    return assets


def _hl_candles(coin, days=15):
    """Pull 5m OHLC for an HL perp (the oracle venue itself)."""
    from httpcompat import http_post
    now = int(time.time() * 1000)
    start = now - int(days * 86400 * 1000)
    r = http_post(HL_INFO, json={"type": "candleSnapshot",
                     "req": {"coin": coin, "interval": "5m",
                             "startTime": start, "endTime": now}}, timeout=20)
    d = r.json()
    if not isinstance(d, list):
        return []
    return [{"t": int(x["t"] / 1000), "o": float(x["o"]), "h": float(x["h"]),
             "l": float(x["l"]), "c": float(x["c"])} for x in d]


# ---- Pyth: oracle feeds for RWA (equities, metals, FX) + crypto ----
# The oracle venue (Pyth) and the data source (Pyth Benchmarks) are the same,
# so "has an oracle" holds by construction — same guarantee as the HL path.
PYTH_TV = "https://benchmarks.pyth.network/v1/shims/tradingview/history"

# Curated set a perp DEX would plausibly list. value=ticker shown in the picker,
# symbol=Pyth TV feed. No upfront history fetch (benchmarks rate-limits hard) —
# history is pulled once, on selection.
RWA_CATALOG = [
    # metals
    ("XAU", "Gold", "Metal.XAU/USD", "Metal"),
    ("XAG", "Silver", "Metal.XAG/USD", "Metal"),
    ("XPT", "Platinum", "Metal.XPT/USD", "Metal"),
    ("XPD", "Palladium", "Metal.XPD/USD", "Metal"),
    # US equities
    ("AAPL", "Apple", "Equity.US.AAPL/USD", "US Equity"),
    ("MSFT", "Microsoft", "Equity.US.MSFT/USD", "US Equity"),
    ("NVDA", "Nvidia", "Equity.US.NVDA/USD", "US Equity"),
    ("TSLA", "Tesla", "Equity.US.TSLA/USD", "US Equity"),
    ("AMZN", "Amazon", "Equity.US.AMZN/USD", "US Equity"),
    ("GOOGL", "Alphabet", "Equity.US.GOOGL/USD", "US Equity"),
    ("META", "Meta", "Equity.US.META/USD", "US Equity"),
    ("COIN", "Coinbase", "Equity.US.COIN/USD", "US Equity"),
    ("MSTR", "Strategy", "Equity.US.MSTR/USD", "US Equity"),
    ("HOOD", "Robinhood", "Equity.US.HOOD/USD", "US Equity"),
    ("GME", "GameStop", "Equity.US.GME/USD", "US Equity"),
    ("SPY", "S&P 500 ETF", "Equity.US.SPY/USD", "US Equity"),
    ("QQQ", "Nasdaq 100 ETF", "Equity.US.QQQ/USD", "US Equity"),
    # FX majors
    ("EUR/USD", "Euro", "FX.EUR/USD", "FX"),
    ("GBP/USD", "Pound", "FX.GBP/USD", "FX"),
    ("USD/JPY", "Yen", "FX.USD/JPY", "FX"),
    ("AUD/USD", "Aussie", "FX.AUD/USD", "FX"),
    ("USD/CAD", "Loonie", "FX.USD/CAD", "FX"),
    ("USD/CHF", "Swissy", "FX.USD/CHF", "FX"),
]
_RWA_BY_VALUE = {v: {"name": v, "desc": d, "symbol": s, "class": c}
                 for (v, d, s, c) in RWA_CATALOG}


def _pyth_candles(tv_symbol, days=15):
    """5m OHLC of the Pyth oracle price via Benchmarks. One retry on 429."""
    from httpcompat import http_get
    now = int(time.time()); start = now - int(days * 86400)
    url = f"{PYTH_TV}?symbol={tv_symbol}&resolution=5&from={start}&to={now}"
    for attempt in range(2):
        r = http_get(url, timeout=25)
        if r.status_code == 429:
            time.sleep(1.5); continue
        d = r.json()
        if d.get("s") != "ok":
            return []
        t, o, h, l, c = (d.get(k, []) for k in ("t", "o", "h", "l", "c"))
        return [{"t": int(t[i]), "o": float(o[i]), "h": float(h[i]),
                 "l": float(l[i]), "c": float(c[i])} for i in range(len(t))]
    return []


def _vol_honest(ev):
    """Annualized vol using the asset's OWN bars/day — so market-hours-only
    RWA feeds aren't inflated by a 24h crypto assumption."""
    if len(ev) < 10:
        return 0
    span_days = max((ev[-1]["t"] - ev[0]["t"]) / 86400, 0.1)
    bpd = len(ev) / span_days
    return round(realized_vol_annual(ev, bars_per_day=bpd))


DATA = HERE / "data"
CACHE = HERE / "fetched"; CACHE.mkdir(exist_ok=True)
NATGAS_TRUTH = {"repeatable_per_day": 28.0, "directional_per_day": 26.0, "fills_per_day": 23.0}

# Reference config = the live NATGAS bot's actual settings at vol ~54%.
# Everything else is scaled off this single calibrated anchor.
_REF_VOL = 54.0


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def suggest_config(vol):
    """Sensible per-asset quoting defaults derived from realized vol.

    Wider spread + tighter inventory as vol rises; depth/ladder held constant
    (those are liquidity-driven, not vol-driven). Anchored on the live NATGAS
    bot's real config at ~54% vol so the numbers aren't made up."""
    r = (vol or _REF_VOL) / _REF_VOL
    return {
        "side_notional_usd": 30000,                       # liquidity, not vol
        "n_levels": 10,
        "min_bps": int(_clamp(round(5 * r), 3, 40)),       # cover adverse selection
        "band_bps": int(_clamp(round(200 * r), 80, 1000)), # ladder reach
        "inv_hard_usd": int(_clamp(round(6000 / r / 500) * 500, 1500, 8000)),  # tighter when risky
        "close_skew_lots": 1000,
        "close_skew_mult": 1.31,
    }

app = Flask(__name__)

_DS = {}
def _load_builtin(name, file):
    if name not in _DS:
        _DS[name] = json.load(open(DATA / file))
    return _DS[name]

BUILTIN = {
    "NATGAS": {"file": "natgas_5m.json", "label": "NATGAS (ground truth)"},
    "VVV":    {"file": "vvv_5m.json",    "label": "VVV / Venice (demo target)"},
}


def _get_events(key):
    if key in BUILTIN:
        return _load_builtin(key, BUILTIN[key]["file"])
    if key in _DS:
        return _DS[key]
    cf = CACHE / f"{key}.json"
    if cf.exists():
        _DS[key] = json.load(open(cf)); return _DS[key]
    return None


@app.get("/")
def index():
    return send_from_directory(HERE, "dashboard.html")


@app.get("/api/exchanges")
def exchanges():
    try:
        from tools._api import cg_request
        sp = cg_request("api/futures/supported-exchange-pairs", params={})
        names = sorted(sp.keys()) if isinstance(sp, dict) else []
        # surface the liquid ones first
        top = [e for e in ["Binance", "Bybit", "OKX", "Bitget", "Hyperliquid",
                           "Coinbase", "Gate", "Kraken"] if e in names]
        rest = [e for e in names if e not in top]
        return jsonify({"ok": True, "exchanges": top + rest})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e),
                        "exchanges": ["Binance", "Bybit", "Bitget"]}), 200


@app.get("/api/oracle_assets")
def oracle_assets():
    """Oracle-backed universe: HL perps (crypto) + Pyth feeds (RWA)."""
    out = []
    # crypto — Hyperliquid oracle
    try:
        for a in _hl_universe():
            ref = f"${a['oracle']}" + (f" · {a['max_lev']}x" if a.get("max_lev") else "")
            out.append({"value": a["name"], "source": "hyperliquid",
                        "symbol": a["name"], "class": "Crypto", "ref": ref})
    except Exception as e:
        pass
    # RWA — Pyth oracle (curated; static, no upfront fetch)
    for v, desc, sym, cls in RWA_CATALOG:
        out.append({"value": v, "source": "pyth", "symbol": sym,
                    "class": cls, "ref": desc})
    return jsonify({"ok": True, "count": len(out), "assets": out})


@app.post("/api/fetch")
def fetch():
    body = request.get_json(force=True)
    source = (body.get("source") or "coinglass").lower()

    # --- oracle-backed path: Hyperliquid perp (oracle venue = data venue) ---
    if source == "hyperliquid":
        coin = (body.get("symbol") or "").strip().upper()
        if not coin:
            return jsonify({"ok": False, "error": "asset required"}), 400
        key = f"HL:{coin}"
        try:
            ev = _hl_candles(coin, days=15)
            if not ev:
                return jsonify({"ok": False, "error": "no oracle candle data for " + coin}), 200
            _DS[key] = ev
            json.dump(ev, open(CACHE / f"{key}.json", "w"))
            span = (ev[-1]["t"] - ev[0]["t"]) / 86400
            vol = _vol_honest(ev)
            return jsonify({"ok": True, "key": key, "label": f"{coin} (HL oracle)",
                            "bars": len(ev), "span_days": round(span, 1),
                            "vol": vol, "last": ev[-1]["c"], "rwa": False,
                            "defaults": suggest_config(vol)})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:160]}), 200

    # --- oracle-backed path: Pyth feed (RWA — equities, metals, FX) ---
    if source == "pyth":
        val = (body.get("symbol") or "").strip().upper()
        meta = _RWA_BY_VALUE.get(val)
        tv = meta["symbol"] if meta else body.get("symbol")
        if not tv:
            return jsonify({"ok": False, "error": "asset required"}), 400
        key = f"PYTH:{val}"
        cls = meta["class"] if meta else "RWA"
        try:
            ev = _pyth_candles(tv, days=15)
            if not ev:
                return jsonify({"ok": False, "error": f"no Pyth oracle history for {val} (or rate-limited — retry)"}), 200
            _DS[key] = ev
            json.dump(ev, open(CACHE / f"{key.replace('/','_')}.json", "w"))
            span = (ev[-1]["t"] - ev[0]["t"]) / 86400
            vol = _vol_honest(ev)
            return jsonify({"ok": True, "key": key,
                            "label": f"{val} · {cls} (Pyth oracle)",
                            "bars": len(ev), "span_days": round(span, 1),
                            "vol": vol, "last": ev[-1]["c"], "rwa": True,
                            "asset_class": cls,
                            "defaults": suggest_config(vol)})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:160]}), 200

    # --- advanced path: arbitrary CoinGlass exchange+symbol ---
    exchange = (body.get("exchange") or "Binance").strip()
    symbol = (body.get("symbol") or "").strip().upper()
    if not symbol:
        return jsonify({"ok": False, "error": "symbol required"}), 400
    key = f"{exchange}:{symbol}"
    try:
        from tools._api import cg_request
        d = cg_request("api/futures/price/history",
                       params={"exchange": exchange, "symbol": symbol,
                               "interval": "5m", "limit": 4500})
        if not isinstance(d, list) or not d:
            return jsonify({"ok": False, "error": "no data for that exchange+symbol"}), 200
        ev = [{"t": int(x["time"] / 1000), "o": float(x["open"]), "h": float(x["high"]),
               "l": float(x["low"]), "c": float(x["close"])} for x in d]
        _DS[key] = ev
        json.dump(ev, open(CACHE / f"{key}.json", "w"))
        span = (ev[-1]["t"] - ev[0]["t"]) / 86400
        vol = round(realized_vol_annual(ev))
        return jsonify({"ok": True, "key": key,
                        "label": f"{symbol} @ {exchange}",
                        "bars": len(ev), "span_days": round(span, 1),
                        "vol": vol, "last": ev[-1]["c"],
                        "defaults": suggest_config(vol)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:160]}), 200


@app.get("/api/assets")
def assets():
    out = []
    for k, v in BUILTIN.items():
        ev = _load_builtin(k, v["file"])
        vol = round(realized_vol_annual(ev))
        out.append({"key": k, "label": v["label"], "builtin": True,
                    "vol": vol, "bars": len(ev), "defaults": suggest_config(vol)})
    for k, ev in _DS.items():
        if k in BUILTIN:
            continue
        vol = round(realized_vol_annual(ev))
        out.append({"key": k, "label": k.replace(":", " @ "), "builtin": False,
                    "vol": vol, "bars": len(ev), "defaults": suggest_config(vol)})
    return jsonify(out)


@app.get("/api/tape")
def tape():
    try:
        return jsonify(json.load(open(HERE / "tape_validation.json")))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/run")
def run():
    body = request.get_json(force=True)
    target_key = body.get("target", "VVV")
    strat = StrategyConfig.from_dict(body.get("strategy", {}))

    ng = _load_builtin("NATGAS", BUILTIN["NATGAS"]["file"])
    tgt = _get_events(target_key)
    if not tgt:
        return jsonify({"error": f"unknown target {target_key}"}), 400
    # align target span to natgas window for apples-to-apples calibration
    span = ng[-1]["t"] - ng[0]["t"]
    tgt = [b for b in tgt if b["t"] >= tgt[-1]["t"] - span]
    if len(tgt) < 20:
        return jsonify({"error": "not enough overlapping data for this asset"}), 200

    fe, ng_sum = calibrate(AssetConfig(symbol="PERP_NATGAS_USDC"), strat, ng,
                           NATGAS_TRUTH["fills_per_day"])
    verdict = trust_score(ng_sum, NATGAS_TRUTH)

    label = target_key.replace(":", "_")
    _, tgt_sum = Engine(AssetConfig(symbol=f"PERP_{label}_USDC"), strat).run(
        tgt, OHLCTouchFill(fill_eff=fe), record=True)

    return jsonify({
        "target": target_key,
        "fill_eff": round(fe, 3),
        "target_vol": _vol_honest(tgt),
        "natgas_vol": _vol_honest(ng),
        "summary": tgt_sum,
        "trust": verdict,
        "calibration": {"sim": ng_sum, "truth": NATGAS_TRUTH},
    })


# ---------- Phase 2: paper-live on Orderly (no keys, public feeds only) ----------
_ORDERLY_SYMS = {"ts": 0, "rows": []}
_PAPER_LOCK = threading.Lock()


def _orderly_symbols():
    if time.time() - _ORDERLY_SYMS["ts"] < 3600 and _ORDERLY_SYMS["rows"]:
        return _ORDERLY_SYMS["rows"]
    from httpcompat import http_get
    r = http_get("https://api.orderly.org/v1/public/futures", timeout=20)
    rows = r.json().get("data", {}).get("rows", [])
    out = sorted([{"symbol": x["symbol"],
                   "token": x["symbol"].replace("PERP_", "").replace("_USDC", ""),
                   "mark": x.get("mark_price"), "vol24": x.get("24h_amount", 0)}
                  for x in rows], key=lambda a: -(a["vol24"] or 0))
    _ORDERLY_SYMS.update(ts=time.time(), rows=out)
    return out


# ---- in-dashboard real-tape validation (repo-forker path; no CLI) ----
import validate_runner as vr

_VAL = {}          # coin -> {"side": float, "strat": dict, "started": ts, "last": dict}
_VAL_LOCK = threading.Lock()
_VAL_STATE = HERE / "shadow" / "_active_validations.json"


def _val_persist():
    try:
        (HERE / "shadow").mkdir(exist_ok=True)
        json.dump({c: {"side": v["side"], "strat": v["strat"], "started": v["started"]}
                   for c, v in _VAL.items()}, open(_VAL_STATE, "w"))
    except Exception:
        pass


def _val_restore():
    try:
        if _VAL_STATE.exists():
            for c, v in json.load(open(_VAL_STATE)).items():
                _VAL[c] = {**v, "last": None}
    except Exception:
        pass


def _val_loop():
    """Every 60s, run one collect cycle per active validation."""
    while True:
        try:
            for coin in list(_VAL.keys()):
                with _VAL_LOCK:
                    v = _VAL.get(coin)
                    if not v:
                        continue
                    try:
                        v["last"] = vr.collect(coin, v["side"], v["strat"])
                    except Exception as e:
                        v["last"] = {"ok": False, "error": str(e)[:120]}
        except Exception:
            pass
        time.sleep(60)


@app.post("/api/validate/start")
def validate_start():
    b = request.get_json(force=True) or {}
    coin = (b.get("coin") or "").strip()
    if not coin:
        return jsonify({"ok": False, "error": "coin required"}), 400
    # Pyth RWA feeds have no public tape — only HL coins are validatable
    if b.get("source") == "pyth":
        return jsonify({"ok": False, "error": "oracle-only asset (no public tape) — "
                        "validation needs a Hyperliquid-listed market"}), 200
    with _VAL_LOCK:
        _VAL[coin] = {"side": float(b.get("side_notional_usd") or 30000),
                      "strat": b.get("strategy") or {}, "started": time.time(),
                      "last": None}
        _val_persist()
    return jsonify({"ok": True, "coin": coin})


@app.post("/api/validate/stop")
def validate_stop():
    b = request.get_json(force=True) or {}
    coin = (b.get("coin") or "").strip()
    with _VAL_LOCK:
        _VAL.pop(coin, None)
        _val_persist()
    return jsonify({"ok": True})


@app.get("/api/validate/status")
def validate_status():
    coin = (request.args.get("coin") or "").strip()
    out = []
    for c in ([coin] if coin else list(_VAL.keys())):
        if not c:
            continue
        try:
            sc = vr.score(c)
        except Exception as e:
            sc = {"ok": False, "error": str(e)[:120]}
        out.append({"coin": c, "active": c in _VAL,
                    "min_fills": vr.MIN_FILLS, "min_days": vr.MIN_DAYS, **(sc or {})})
    return jsonify({"ok": True, "validations": out})


@app.get("/api/paper/symbols")
def paper_symbols():
    try:
        return jsonify({"ok": True, "symbols": _orderly_symbols()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:160], "symbols": []}), 200


@app.post("/api/paper/start")
def paper_start():
    b = request.get_json(force=True)
    sym = (b.get("symbol") or "").strip().upper()
    if not sym.startswith("PERP_"):
        return jsonify({"ok": False, "error": "need an Orderly PERP symbol"}), 200
    strat = b.get("strategy", {}) or {}
    side = float(b.get("side_notional_usd", strat.get("side_notional_usd", 30000)))
    with _PAPER_LOCK:
        pl.reset_session(sym)              # fresh, flat start
        pl.save_cfg(sym, side, strat)
        pl.set_active(sym, True)
        pl.collect_one(sym)                # establishes the baseline immediately
    return jsonify({"ok": True, "symbol": sym, "started": True})


@app.post("/api/paper/stop")
def paper_stop():
    b = request.get_json(force=True)
    sym = (b.get("symbol") or "").strip().upper()
    with _PAPER_LOCK:
        pl.set_active(sym, False)
    return jsonify({"ok": True, "symbol": sym, "stopped": True})


@app.get("/api/paper/status")
def paper_status():
    syms = pl.list_active()
    sessions = [pl.status_one(s) for s in syms]
    sessions.sort(key=lambda x: -x["running_min"])
    return jsonify({"ok": True, "count": len(sessions), "sessions": sessions})


def _paper_loop():
    """Background collector: every 60s, advance each active paper session."""
    while True:
        try:
            for sym in pl.list_active():
                with _PAPER_LOCK:
                    pl.collect_one(sym)
        except Exception:
            pass
        time.sleep(60)


if __name__ == "__main__":
    t = threading.Thread(target=_paper_loop, daemon=True)
    t.start()
    _val_restore()
    threading.Thread(target=_val_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "7011")), threaded=True)
