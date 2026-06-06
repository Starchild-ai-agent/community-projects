from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from datetime import datetime, timezone
import os, sys, json, xml.etree.ElementTree as ET

from core.http_client import proxied_get

import importlib.util


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(m)
    return m


coinglass = _load_module("coinglass", "/data/workspace/skills/coinglass/exports.py")
twelvedata = _load_module("twelvedata", "/data/workspace/skills/twelvedata/exports.py")

funding_rate = coinglass.funding_rate
cg_open_interest = coinglass.cg_open_interest
cg_liquidations = coinglass.cg_liquidations
cg_hyperliquid_whale_alerts = coinglass.cg_hyperliquid_whale_alerts

twelvedata_quote = twelvedata.twelvedata_quote
twelvedata_quote_batch = twelvedata.twelvedata_quote_batch

app = FastAPI(title="WhaleFlow Terminal")
CALLER_ID = "preview:whaleflow-terminal"

# ── State ──────────────────────────────────────────────────────────────────

_prev_regime = {"label": "Mixed", "score": 0}
_alert_log: list[dict] = []
_rules = {
    "whale_notional_usd": 500_000,   # fire when whale position > this
    "liq_spike_usd": 50_000_000,     # fire when 24h liquidations > this (per symbol)
    "oi_spike_pct": 5.0,             # fire when OI change % > this (per symbol)
    "funding_spike_pct": 0.01,       # fire when funding rate abs value > this
    "regime_flip": True,             # fire when regime flips Risk-On↔Risk-Off
}

_seen_whale_hashes: set[str] = set()
_alert_cooldown: dict[str, float] = {}  # key → last fired unix

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def parse_rate_to_float(rate_str):
    if not rate_str:
        return 0.0
    return safe_float(str(rate_str).replace("%", "").replace("+", "").strip())


def _cooldown(key: str, seconds: int = 300) -> bool:
    """Return True if enough time has passed since last fire. Also updates last-fire time."""
    import time
    now = time.time()
    last = _alert_cooldown.get(key, 0)
    if now - last >= seconds:
        _alert_cooldown[key] = now
        return True
    return False


def _push_alert(event_type: str, severity: str, title: str, body: str, meta: dict | None = None):
    """Record an alert and keep the last 50."""
    entry = {
        "id": len(_alert_log),
        "timestamp": now_iso(),
        "event_type": event_type,
        "severity": severity,   # info | warn | critical
        "title": title,
        "body": body,
        "meta": meta or {},
    }
    _alert_log.insert(0, entry)
    if len(_alert_log) > 50:
        _alert_log = _alert_log[:50]


# ── Alert rules ─────────────────────────────────────────────────────────────

class RulesModel(BaseModel):
    whale_notional_usd: float | None = None
    liq_spike_usd: float | None = None
    oi_spike_pct: float | None = None
    funding_spike_pct: float | None = None
    regime_flip: bool | None = None


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/api/snapshot")
def snapshot():
    global _prev_regime

    try:
        crypto = get_crypto_block()
        tradfi = get_tradfi_block()
        news = get_news_block()
        regime = build_regime(crypto["rows"], tradfi)

        # ── Alert: regime flip ──────────────────────────────────────────────
        if _rules.get("regime_flip") and regime["label"] != _prev_regime["label"]:
            if regime["label"] in ("Risk-On", "Risk-Off") and _cooldown("regime_flip", 600):
                _push_alert(
                    "regime_flip",
                    "warn",
                    f"Regime flipped → {regime['label']}",
                    f"Score moved from {_prev_regime['score']} to {regime['score']}. "
                    f"Crypto bias: {crypto['rows'][0]['whale_bias'] if crypto['rows'] else 'n/a'}",
                    {"from_label": _prev_regime["label"], "to_label": regime["label"],
                     "from_score": _prev_regime["score"], "to_score": regime["score"]}
                )

        _prev_regime = regime

        # ── Per-symbol alerts (crypto block built above) ────────────────────
        active_alerts = []

        for row in crypto["rows"]:
            sym = row["symbol"]

            # Whale notional
            for w in crypto.get("top_whales", []):
                if w.get("symbol") == sym:
                    nv = safe_float(w.get("position_value_usd", 0))
                    if nv >= _rules.get("whale_notional_usd", 500_000):
                        key = f"whale:{w['symbol']}:{round(nv/10000)}"
                        if _cooldown(key, 600):
                            side = "Long" if safe_float(w.get("position_size", 0)) > 0 else "Short"
                            _push_alert(
                                "whale_large",
                                "info",
                                f"🦋 {sym} whale {side}: ${nv/1e6:.1f}M",
                                f"Entry ${safe_float(w.get('entry_price')):.2f} · Liq ${safe_float(w.get('liq_price')):.2f}",
                                {"symbol": sym, "notional_usd": nv, "side": side}
                            )

            # OI spike
            oi_ch = row.get("oi_change_pct", 0)
            if abs(oi_ch) >= _rules.get("oi_spike_pct", 5.0):
                key = f"oi_spike:{sym}"
                if _cooldown(key, 600):
                    direction = "surge" if oi_ch > 0 else "drop"
                    _push_alert(
                        "oi_spike",
                        "warn" if abs(oi_ch) > 10 else "info",
                        f"📊 OI {direction}: {sym} {abs(oi_ch):.1f}%",
                        f"Open interest changed {abs(oi_ch):.1f}% in the period.",
                        {"symbol": sym, "oi_change_pct": oi_ch}
                    )

            # Funding spike
            fr = row.get("funding_pct", 0)
            if abs(fr) >= _rules.get("funding_spike_pct", 0.01):
                key = f"funding:{sym}"
                if _cooldown(key, 600):
                    direction = "positive" if fr > 0 else "negative"
                    _push_alert(
                        "funding_spike",
                        "warn" if abs(fr) > 0.03 else "info",
                        f"💰 Funding {direction}: {sym} {fr:.4f}%",
                        f"Funding rate is {fr:.4f}% (annualized ~{fr*365*3:.1f}%)",
                        {"symbol": sym, "funding_pct": fr}
                    )

            # Liquidation spike
            liq = row.get("liq_24h_usd", 0)
            if liq >= _rules.get("liq_spike_usd", 50_000_000):
                key = f"liq:{sym}"
                if _cooldown(key, 600):
                    long_liq = row.get("long_liq_usd", 0)
                    short_liq = row.get("short_liq_usd", 0)
                    dominant = "long" if long_liq > short_liq else "short"
                    _push_alert(
                        "liq_spike",
                        "critical" if liq > 200_000_000 else "warn",
                        f"🔥 Liquidation cluster: {sym} ${liq/1e6:.1f}M",
                        f"24h liquidations ${liq/1e6:.1f}M — {dominant} side dominant.",
                        {"symbol": sym, "liq_usd": liq, "long_liq_usd": long_liq,
                         "short_liq_usd": short_liq}
                    )

        active_alerts = _alert_log[:10]

        return {
            "updated_at": now_iso(),
            "crypto": crypto,
            "tradfi": tradfi,
            "news": news,
            "regime": regime,
            "alerts": active_alerts,
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"updated_at": now_iso(), "error": "Snapshot fetch failed", "details": str(e)},
        )


@app.get("/api/alerts")
def get_alerts(limit: int = 20):
    return {"alerts": _alert_log[:limit], "total": len(_alert_log)}


@app.post("/api/alerts/clear")
def clear_alerts():
    global _alert_log, _alert_cooldown
    count = len(_alert_log)
    _alert_log = []
    _alert_cooldown = {}
    return {"ok": True, "cleared": count}


@app.get("/api/rules")
def get_rules():
    return {"rules": _rules}


@app.post("/api/rules")
def update_rules(rules: RulesModel):
    global _rules
    update = rules.model_dump(exclude_none=True)
    _rules.update(update)
    return {"ok": True, "rules": _rules}


# ── Data fetch helpers ──────────────────────────────────────────────────────

def get_crypto_block():
    symbols = ["BTC", "ETH", "SOL"]
    rows = []

    for s in symbols:
        fr = funding_rate(symbol=s)
        oi = cg_open_interest(symbol=s)
        liq = cg_liquidations(symbol=s, time_type="h24")

        all_oi = oi[0] if isinstance(oi, list) and oi else {}
        all_liq = liq[0] if isinstance(liq, list) and liq else {}

        rate = parse_rate_to_float(fr.get("rate") if isinstance(fr, dict) else "0%")
        oi_change = safe_float(all_oi.get("oichangePercent", 0))
        liq_total = safe_float(all_liq.get("liquidation_usd", 0))
        long_liq = safe_float(all_liq.get("longLiquidation_usd", 0))
        short_liq = safe_float(all_liq.get("shortLiquidation_usd", 0))

        score = 0
        if rate > 0: score += 1
        elif rate < 0: score -= 1
        if oi_change > 0: score += 1
        elif oi_change < 0: score -= 1
        if short_liq > long_liq * 1.1: score += 1
        elif long_liq > short_liq * 1.1: score -= 1

        bias = "Neutral"
        if score >= 2: bias = "Bullish"
        elif score <= -2: bias = "Bearish"

        rows.append({
            "symbol": s, "funding_pct": rate, "oi_change_pct": oi_change,
            "liq_24h_usd": liq_total, "long_liq_usd": long_liq,
            "short_liq_usd": short_liq, "whale_bias": bias,
        })

    whales = cg_hyperliquid_whale_alerts() or []
    top_whales = sorted(whales, key=lambda x: abs(safe_float(x.get("position_value_usd", 0))), reverse=True)[:8]

    return {"rows": rows, "whale_alert_count": len(whales), "top_whales": top_whales}


def get_tradfi_block():
    batch_symbols = "SPY,QQQ,DIA,EUR/USD,USD/JPY,XAU/USD,XAG/USD,WTI/USD"
    out = []

    try:
        batch = twelvedata_quote_batch(symbols=batch_symbols)
        if isinstance(batch, dict) and "code" not in batch:
            for k, v in batch.items():
                if isinstance(v, dict):
                    out.append({
                        "symbol": k,
                        "price": safe_float(v.get("close", 0)),
                        "change_pct": safe_float(v.get("percent_change", 0)),
                        "source": "TwelveData",
                    })
    except Exception:
        pass

    if not out:
        for s in ["SPY", "QQQ", "EUR/USD", "USD/JPY", "XAU/USD", "WTI/USD"]:
            try:
                q = twelvedata_quote(symbol=s)
                out.append({
                    "symbol": s,
                    "price": safe_float(q.get("close", 0)),
                    "change_pct": safe_float(q.get("percent_change", 0)),
                    "source": "TwelveData",
                })
            except Exception:
                continue

    return out


def fetch_rss(url, source, limit=6):
    try:
        r = proxied_get(url, headers={"SC-CALLER-ID": CALLER_ID}, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        items = []
        for node in root.findall(".//item")[:limit]:
            title = (node.findtext("title") or "").strip()
            link = (node.findtext("link") or "").strip()
            pub = (node.findtext("pubDate") or "").strip()
            if title and link:
                items.append({"title": title, "url": link, "source": source, "published": pub})
        return items
    except Exception:
        return []


def get_news_block():
    feeds = [
        ("https://feeds.reuters.com/reuters/businessNews", "Reuters"),
        ("https://www.cnbc.com/id/100003114/device/rss/rss.html", "CNBC"),
        ("https://www.coindesk.com/arc/outboundfeeds/rss/", "CoinDesk"),
    ]
    all_items = []
    for url, src in feeds:
        all_items.extend(fetch_rss(url, src, limit=5))
    seen = set()
    deduped = []
    for x in all_items:
        if x["url"] not in seen:
            seen.add(x["url"])
            deduped.append(x)
    return deduped[:12]


def build_regime(crypto_rows, tradfi_rows):
    score = 0
    for r in crypto_rows:
        if r["whale_bias"] == "Bullish": score += 1
        elif r["whale_bias"] == "Bearish": score -= 1
    for t in tradfi_rows:
        sym = t.get("symbol", "")
        ch = safe_float(t.get("change_pct", 0))
        if sym in ("SPY", "QQQ", "DIA"):
            score += 1 if ch > 0 else -1
        if sym == "XAU/USD" and ch > 0.4:
            score -= 1

    if score >= 3: label = "Risk-On"
    elif score <= -3: label = "Risk-Off"
    else: label = "Mixed"

    return {"label": label, "score": score}