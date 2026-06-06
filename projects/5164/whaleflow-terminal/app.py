from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from datetime import datetime, timezone
import os
import sys
import xml.etree.ElementTree as ET

from core.http_client import proxied_get

import importlib.util


def _load_module(module_name: str, file_path: str):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


coinglass_exports = _load_module("coinglass_exports", "/data/workspace/skills/coinglass/exports.py")
twelvedata_exports = _load_module("twelvedata_exports", "/data/workspace/skills/twelvedata/exports.py")

funding_rate = coinglass_exports.funding_rate
cg_open_interest = coinglass_exports.cg_open_interest
cg_liquidations = coinglass_exports.cg_liquidations
cg_hyperliquid_whale_alerts = coinglass_exports.cg_hyperliquid_whale_alerts

twelvedata_quote = twelvedata_exports.twelvedata_quote
twelvedata_quote_batch = twelvedata_exports.twelvedata_quote_batch

app = FastAPI(title="WhaleFlow Terminal")

CALLER_ID = "preview:whaleflow-terminal"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_rate_to_float(rate_str: str) -> float:
    if not rate_str:
        return 0.0
    cleaned = str(rate_str).replace("%", "").replace("+", "").strip()
    try:
        return float(cleaned)
    except Exception:
        return 0.0


def safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def get_crypto_block():
    symbols = ["BTC", "ETH", "SOL"]
    rows = []

    for s in symbols:
        fr = funding_rate(symbol=s)
        oi = cg_open_interest(symbol=s)
        liq = cg_liquidations(symbol=s, time_type="h24")

        all_oi = oi[0] if isinstance(oi, list) and oi else {}
        all_liq = liq[0] if isinstance(liq, list) and liq else {}

        rate_raw = fr.get("rate") if isinstance(fr, dict) else "0%"
        rate = parse_rate_to_float(rate_raw)

        oi_change = safe_float(all_oi.get("oichangePercent", 0))
        liq_total = safe_float(all_liq.get("liquidation_usd", 0))
        long_liq = safe_float(all_liq.get("longLiquidation_usd", 0))
        short_liq = safe_float(all_liq.get("shortLiquidation_usd", 0))

        whale_bias = "Neutral"
        score = 0
        if rate > 0:
            score += 1
        elif rate < 0:
            score -= 1

        if oi_change > 0:
            score += 1
        elif oi_change < 0:
            score -= 1

        if short_liq > long_liq * 1.1:
            score += 1
        elif long_liq > short_liq * 1.1:
            score -= 1

        if score >= 2:
            whale_bias = "Bullish"
        elif score <= -2:
            whale_bias = "Bearish"

        rows.append(
            {
                "symbol": s,
                "funding_pct": rate,
                "oi_change_pct": oi_change,
                "liq_24h_usd": liq_total,
                "long_liq_usd": long_liq,
                "short_liq_usd": short_liq,
                "whale_bias": whale_bias,
            }
        )

    whales = cg_hyperliquid_whale_alerts()
    whales = whales if isinstance(whales, list) else []

    top_whales = sorted(
        whales,
        key=lambda x: abs(safe_float(x.get("position_value_usd", 0))),
        reverse=True,
    )[:8]

    return {
        "rows": rows,
        "whale_alert_count": len(whales),
        "top_whales": top_whales,
    }


def get_tradfi_block():
    batch_symbols = "SPY,QQQ,DIA,EUR/USD,USD/JPY,XAU/USD,XAG/USD,WTI/USD"

    out = []

    try:
        batch = twelvedata_quote_batch(symbols=batch_symbols)
        if isinstance(batch, dict) and "code" not in batch:
            for k, v in batch.items():
                if isinstance(v, dict):
                    out.append(
                        {
                            "symbol": k,
                            "price": safe_float(v.get("close", 0)),
                            "change_pct": safe_float(v.get("percent_change", 0)),
                            "source": "TwelveData",
                        }
                    )
    except Exception:
        pass

    if not out:
        fallback = ["SPY", "QQQ", "EUR/USD", "USD/JPY", "XAU/USD", "WTI/USD"]
        for s in fallback:
            try:
                q = twelvedata_quote(symbol=s)
                out.append(
                    {
                        "symbol": s,
                        "price": safe_float(q.get("close", 0)),
                        "change_pct": safe_float(q.get("percent_change", 0)),
                        "source": "TwelveData",
                    }
                )
            except Exception:
                continue

    return out


def fetch_rss(url: str, source: str, limit=6):
    try:
        r = proxied_get(url, headers={"SC-CALLER-ID": CALLER_ID}, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.text)

        items = []
        for node in root.findall(".//item")[:limit]:
            title = (node.findtext("title") or "").strip()
            link = (node.findtext("link") or "").strip()
            pub_date = (node.findtext("pubDate") or "").strip()
            if title and link:
                items.append(
                    {
                        "title": title,
                        "url": link,
                        "source": source,
                        "published": pub_date,
                    }
                )
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
    for url, source in feeds:
        all_items.extend(fetch_rss(url, source, limit=5))

    seen = set()
    deduped = []
    for x in all_items:
        key = x["url"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(x)

    return deduped[:12]


def build_regime(crypto_rows, tradfi_rows):
    risk_on_score = 0

    for r in crypto_rows:
        if r["whale_bias"] == "Bullish":
            risk_on_score += 1
        elif r["whale_bias"] == "Bearish":
            risk_on_score -= 1

    for t in tradfi_rows:
        sym = t.get("symbol", "")
        ch = safe_float(t.get("change_pct", 0))
        if sym in ("SPY", "QQQ", "DIA"):
            risk_on_score += 1 if ch > 0 else -1
        if sym == "XAU/USD":
            risk_on_score -= 1 if ch > 0.4 else 0

    if risk_on_score >= 3:
        regime = "Risk-On"
    elif risk_on_score <= -3:
        regime = "Risk-Off"
    else:
        regime = "Mixed"

    return {"label": regime, "score": risk_on_score}


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/api/snapshot")
def snapshot():
    try:
        crypto = get_crypto_block()
        tradfi = get_tradfi_block()
        news = get_news_block()
        regime = build_regime(crypto["rows"], tradfi)

        return {
            "updated_at": now_iso(),
            "crypto": crypto,
            "tradfi": tradfi,
            "news": news,
            "regime": regime,
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "updated_at": now_iso(),
                "error": "Snapshot fetch failed",
                "details": str(e),
            },
        )
