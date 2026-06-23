"""
Market data fetchers — wraps OrderlyClient for analysis-ready data.
"""
from client import OrderlyClient
import datetime


def get_top_markets(client, min_volume_usd=1_000_000, limit=15):
    """Return liquid perp markets sorted by 24h USD volume."""
    resp = client.get_all_markets()
    rows = resp.get("data", {}).get("rows", [])
    liquid = [r for r in rows if r.get("24h_amount", 0) >= min_volume_usd]
    liquid.sort(key=lambda r: r.get("24h_amount", 0), reverse=True)
    return liquid[:limit]


def get_funding_summary(client, symbols):
    """Current funding rates for a list of symbols."""
    out = []
    for s in symbols:
        resp = client.get_market(s)
        rows = resp.get("data", {}).get("rows", [])
        for r in rows:
            if r.get("symbol") == s:
                out.append({
                    "symbol": s,
                    "est_funding_rate": r.get("est_funding_rate"),
                    "last_funding_rate": r.get("last_funding_rate"),
                    "next_funding_time": r.get("next_funding_time"),
                    "open_interest": r.get("open_interest"),
                    "mark_price": r.get("mark_price"),
                    "24h_amount": r.get("24h_amount"),
                })
                break
    return out


def get_orderbook_imbalance(client, symbol, depth=20):
    """Bid/ask volume imbalance. >0 = more bids (buy pressure)."""
    resp = client.get_orderbook(symbol, depth=depth)
    data = resp.get("data", {})
    bids = data.get("bids", [])
    asks = data.get("asks", [])
    bid_vol = sum(float(b["quantity"]) for b in bids) if bids else 0
    ask_vol = sum(float(a["quantity"]) for a in asks) if asks else 0
    total = bid_vol + ask_vol
    imbalance = (bid_vol - ask_vol) / total if total > 0 else 0
    return {
        "symbol": symbol,
        "bid_volume": bid_vol,
        "ask_volume": ask_vol,
        "imbalance": imbalance,  # -1..1
        "spread": float(data.get("spread", 0)),
        "mid_price": float(data.get("mid_price", 0)),
    }


def get_recent_candles(client, symbol, interval="1h", limit=100):
    resp = client.get_candles(symbol, interval=interval, limit=limit)
    rows = resp.get("data", {}).get("rows", [])
    # normalize to floats + chronological order (oldest first)
    out = []
    for r in rows:
        out.append({
            "timestamp": int(float(r["timestamp"])),
            "time": datetime.datetime.utcfromtimestamp(int(float(r["timestamp"]))/1000).strftime("%Y-%m-%d %H:%M"),
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": float(r["volume"]),
        })
    out.sort(key=lambda x: x["timestamp"])
    return out


def compute_atr(candles, period=14):
    """Average True Range over last N candles."""
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        h, l, pc = candles[i]["high"], candles[i]["low"], candles[i-1]["close"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    return sum(trs[-period:]) / period


def compute_rsi(candles, period=14):
    """Relative Strength Index."""
    if len(candles) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(candles)):
        chg = candles[i]["close"] - candles[i-1]["close"]
        gains.append(max(chg, 0))
        losses.append(max(-chg, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


if __name__ == "__main__":
    c = OrderlyClient()
    print("=== Top liquid markets ===")
    for m in get_top_markets(c, limit=10):
        print(f"{m['symbol']:25} price={m['mark_price']:>12}  24h_vol=${m['24h_amount']:>14,.0f}  funding={m['est_funding_rate']:.6f}")

    print("\n=== BTC orderbook imbalance ===")
    print(get_orderbook_imbalance(c, "PERP_BTC_USDC"))

    print("\n=== BTC 1h candles (last 6) + ATR + RSI ===")
    candles = get_recent_candles(c, "PERP_BTC_USDC", "1h", 50)
    for cd in candles[-6:]:
        print(f"{cd['time']}  c={cd['close']:.1f}  v={cd['volume']:.2f}")
    print(f"ATR(14)={compute_atr(candles):.2f}  RSI(14)={compute_rsi(candles):.1f}")
