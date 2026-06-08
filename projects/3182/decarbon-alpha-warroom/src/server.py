#!/usr/bin/env python3
import json
import math
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = 8765
CALLER_ID = "preview:decarbon-alpha-warroom"

ROOT = Path(__file__).resolve().parent
SKILL_PATH = "/data/workspace/skills/twelvedata"
if SKILL_PATH not in sys.path:
    sys.path.insert(0, SKILL_PATH)

from exports import twelvedata_quote_batch, twelvedata_time_series  # noqa: E402

BENCHMARKS = ["SPY", "QQQ", "SOXX", "XLK", "XLV", "XLF"]
CANDIDATES = [
    "VRT", "GEV", "PTC", "PCOR", "DLR", "TT", "ETN", "J",
    "DELL", "HPE", "SMCI", "NBIS", "CRWV", "CDNS", "EQIX"
]


def _f(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def _quote_batch(symbols):
    data = twelvedata_quote_batch(symbols=",".join(symbols))
    if isinstance(data, dict) and "data" in data:
        rows = data.get("data", [])
        if isinstance(rows, list):
            return {r.get("symbol"): r for r in rows if isinstance(r, dict)}
    if isinstance(data, dict):
        return data
    return {}


def _regime(bench):
    spy = _f(bench.get("SPY", {}).get("percent_change"))
    qqq = _f(bench.get("QQQ", {}).get("percent_change"))
    soxx = _f(bench.get("SOXX", {}).get("percent_change"))
    xlk = _f(bench.get("XLK", {}).get("percent_change"))
    xlv = _f(bench.get("XLV", {}).get("percent_change"))

    if spy <= -2.0 or qqq <= -3.0 or soxx <= -7.0:
        return "PANIC"
    if (spy <= -1.0 and qqq <= -1.8) or (xlk < 0 and xlv > 0):
        return "RISK_OFF"
    return "RISK_ON"


def _series_metrics(symbol):
    ts = twelvedata_time_series(symbol=symbol, interval="1day", outputsize=65)
    values = ts.get("values", []) if isinstance(ts, dict) else []
    closes = [_f(v.get("close")) for v in values if isinstance(v, dict) and v.get("close") is not None]
    if len(closes) < 25:
        return None
    latest = closes[0]
    high60 = max(closes[:60])
    ma20 = sum(closes[:20]) / 20
    dd60 = (latest / high60 - 1) * 100
    dist20 = (latest / ma20 - 1) * 100
    return {"latest": latest, "dd60": dd60, "dist20": dist20}


def _build_row(symbol, q, m, regime):
    px = _f(q.get("close") or q.get("price") or m["latest"])
    day = _f(q.get("percent_change"))
    dd = m["dd60"]
    dist20 = m["dist20"]

    first_low = round(px * 0.98, 2)
    first_high = round(px * 1.01, 2)
    first_ref = (first_low + first_high) / 2
    add1 = round(first_ref * 0.92, 2)
    add2 = round(first_ref * 0.85, 2)
    stop = round(add2 * 0.94, 2)

    base_upside = max(0.16, min(0.32, abs(dd) / 100 + 0.14))
    target = round(px * (1 + base_upside), 2)
    upside = round((target / px - 1) * 100, 1)

    if regime == "PANIC":
        action = "WATCH"
    elif dd < -10 and -10 <= dist20 <= 1 and day > -8:
        action = "BUY_NOW"
    elif dd < -6:
        action = "WATCH"
    else:
        action = "AVOID"

    if symbol in {"SMCI", "NBIS", "CRWV"} and regime != "RISK_ON":
        action = "AVOID"

    if action == "BUY_NOW":
        tranche_weights = [0.5, 0.3, 0.2]
    elif action == "WATCH":
        tranche_weights = [0.4, 0.3, 0.3]
    else:
        tranche_weights = [0.0, 0.0, 0.0]

    total_capital = 100000.0
    tranche_amounts = [round(total_capital * w, 2) for w in tranche_weights]

    def _shares(amount, price):
        if price <= 0:
            return 0
        return int(math.floor(amount / price))

    shares_first = _shares(tranche_amounts[0], first_ref)
    shares_add1 = _shares(tranche_amounts[1], add1)
    shares_add2 = _shares(tranche_amounts[2], add2)

    return {
        "ticker": symbol,
        "current": round(px, 2),
        "day_change_pct": round(day, 2),
        "first_buy": f"{first_low}-{first_high}",
        "add1": add1,
        "add2": add2,
        "stop": stop,
        "target": target,
        "upside_pct": upside,
        "regime_tag": regime,
        "action": action,
        "drawdown_60d_pct": round(dd, 2),
        "capital_total": total_capital,
        "amount_first": tranche_amounts[0],
        "amount_add1": tranche_amounts[1],
        "amount_add2": tranche_amounts[2],
        "shares_first": shares_first,
        "shares_add1": shares_add1,
        "shares_add2": shares_add2,
    }


def build_snapshot():
    bench = _quote_batch(BENCHMARKS)
    regime = _regime(bench)
    quotes = _quote_batch(CANDIDATES)

    rows = []
    for s in CANDIDATES:
        try:
            metrics = _series_metrics(s)
            if not metrics:
                continue
            q = quotes.get(s, {}) if isinstance(quotes, dict) else {}
            rows.append(_build_row(s, q, metrics, regime))
        except Exception:
            continue

    rows.sort(key=lambda r: (r["action"] != "BUY_NOW", r["drawdown_60d_pct"]))

    return {
        "asof_utc": datetime.now(timezone.utc).isoformat(),
        "regime": regime,
        "benchmarks": {
            k: {
                "close": _f(v.get("close")),
                "percent_change": _f(v.get("percent_change")),
            }
            for k, v in bench.items()
            if isinstance(v, dict)
        },
        "rows": rows,
    }


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload, code=200):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_file(self, path: Path, ctype: str = "text/html; charset=utf-8"):
        if not path.exists():
            self.send_error(404)
            return
        raw = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send_file(ROOT / "index.html")
        if self.path == "/api/snapshot":
            try:
                return self._send_json(build_snapshot())
            except Exception as e:
                return self._send_json({"error": str(e), "rows": []}, 500)
        self.send_error(404)


if __name__ == "__main__":
    os.environ.setdefault("SC_CALLER_ID", CALLER_ID)
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"warroom serving on 127.0.0.1:{PORT}")
    server.serve_forever()
