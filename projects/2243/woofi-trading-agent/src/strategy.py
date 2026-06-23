"""
Mean Reversion + Funding Filter strategy.

Signal logic:
  1. Detect range over last N candles (high/low).
  2. If price in support band + RSI oversold → LONG candidate.
  3. If price in resistance band + RSI overbought → SHORT candidate.
  4. Confirm with orderbook imbalance (bids > asks for longs, vice versa).
  5. Filter: skip if funding is elevated or extreme.
  6. Compute stop/target from ATR.

Returns a Signal dict or None.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from market_data import (
    get_recent_candles, compute_atr, compute_rsi, get_orderbook_imbalance
)
from client import OrderlyClient
import yaml
from datetime import datetime, timezone


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "strategy.yaml")


def load_strategy_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def detect_range(candles, lookback=50):
    """Return (range_high, range_low, width_pct, age_hours) or None."""
    if len(candles) < lookback:
        lookback = len(candles)
    recent = candles[-lookback:]
    hi = max(c["high"] for c in recent)
    lo = min(c["low"] for c in recent)
    width_pct = (hi - lo) / lo * 100 if lo > 0 else 0
    # age: hours spanned by the window
    age_hours = (recent[-1]["timestamp"] - recent[0]["timestamp"]) / 3_600_000
    return hi, lo, width_pct, age_hours


def count_touches(candles, level, tolerance_pct=0.5, side="support"):
    """Count how many times price touched a level within tolerance."""
    touches = 0
    tol = level * tolerance_pct / 100
    for c in candles:
        if side == "support" and c["low"] <= level + tol:
            touches += 1
        elif side == "resistance" and c["high"] >= level - tol:
            touches += 1
    return touches


def evaluate_signal(client, symbol, cfg=None):
    """
    Evaluate strategy for a symbol. Returns Signal dict or None (no trade).
    """
    if cfg is None:
        cfg = load_strategy_config()
    s = cfg["strategy"]

    # --- Fetch data ---
    candles = get_recent_candles(client, symbol, cfg["market_data"]["candle_interval"], cfg["market_data"]["candle_lookback"])
    if len(candles) < s["range_lookback"]:
        return {"symbol": symbol, "action": "SKIP", "reason": f"insufficient candles ({len(candles)})"}

    atr = compute_atr(candles, 14)
    rsi = compute_rsi(candles, 14)
    last_price = candles[-1]["close"]

    # --- Range detection ---
    range_hi, range_lo, width_pct, age_h = detect_range(candles, s["range_lookback"])
    if width_pct > s["max_range_width_pct"]:
        return {"symbol": symbol, "action": "SKIP", "reason": f"range too wide ({width_pct:.1f}% > {s['max_range_width_pct']}%)"}
    if age_h < s["min_range_age_hours"]:
        return {"symbol": symbol, "action": "SKIP", "reason": f"range too young ({age_h:.1f}h)"}

    # count touches
    sup_touches = count_touches(candles[-s["range_lookback"]:], range_lo, side="support")
    res_touches = count_touches(candles[-s["range_lookback"]:], range_hi, side="resistance")
    if sup_touches < s["min_range_touches"] or res_touches < s["min_range_touches"]:
        return {"symbol": symbol, "action": "SKIP", "reason": f"insufficient touches (sup={sup_touches}, res={res_touches})"}

    # --- Position in range ---
    range_size = range_hi - range_lo
    sup_band = range_lo + range_size * (s["entry"]["support_band_pct"] / 100)
    res_band = range_hi - range_size * (s["entry"]["resistance_band_pct"] / 100)

    direction = None
    if last_price <= sup_band and rsi < s["entry"]["rsi_oversold"]:
        direction = "LONG"
    elif last_price >= res_band and rsi > s["entry"]["rsi_overbought"]:
        direction = "SHORT"

    if direction is None:
        return {
            "symbol": symbol, "action": "SKIP",
            "reason": f"no entry trigger (price={last_price:.1f}, sup_band={sup_band:.1f}, res_band={res_band:.1f}, RSI={rsi:.1f})"
        }

    # --- Funding filter ---
    market = client.get_market(symbol)
    rows = market.get("data", {}).get("rows", [])
    funding_rate = None
    for r in rows:
        if r.get("symbol") == symbol:
            funding_rate = r.get("est_funding_rate")
            break
    if funding_rate is None:
        return {"symbol": symbol, "action": "SKIP", "reason": "no funding data"}

    fr_bps = funding_rate * 10000
    ff = s["funding_filter"]
    if abs(fr_bps) > ff["extreme_funding_bps"]:
        return {"symbol": symbol, "action": "SKIP", "reason": f"funding extreme ({fr_bps:.1f}bps)"}
    if direction == "LONG" and fr_bps > ff["max_long_funding_bps"]:
        return {"symbol": symbol, "action": "SKIP", "reason": f"funding too high for long ({fr_bps:.1f}bps)"}
    if direction == "SHORT" and fr_bps < -ff["max_short_funding_bps"]:
        return {"symbol": symbol, "action": "SKIP", "reason": f"funding too negative for short ({fr_bps:.1f}bps)"}

    # --- Orderbook confirmation ---
    if s["entry"]["require_ob_confirmation"]:
        ob = get_orderbook_imbalance(client, symbol, cfg["market_data"]["orderbook_depth"])
        imb = ob["imbalance"]
        min_imb = s["entry"]["min_ob_imbalance"]
        if direction == "LONG" and imb < min_imb:
            return {"symbol": symbol, "action": "SKIP", "reason": f"OB imbalance not confirming long ({imb:+.3f})"}
        if direction == "SHORT" and imb > -min_imb:
            return {"symbol": symbol, "action": "SKIP", "reason": f"OB imbalance not confirming short ({imb:+.3f})"}

    # --- Compute entry/stop/target ---
    if direction == "LONG":
        entry = last_price
        stop = entry - s["exit"]["stop_loss_atr_mult"] * atr
        target = entry + s["exit"]["take_profit_atr_mult"] * atr
    else:
        entry = last_price
        stop = entry + s["exit"]["stop_loss_atr_mult"] * atr
        target = entry - s["exit"]["take_profit_atr_mult"] * atr

    return {
        "symbol": symbol,
        "action": "TRADE",
        "direction": direction,
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "target": round(target, 2),
        "atr": round(atr, 2),
        "rsi": round(rsi, 1),
        "funding_bps": round(fr_bps, 2),
        "range_high": round(range_hi, 2),
        "range_low": round(range_lo, 2),
        "range_width_pct": round(width_pct, 2),
        "ob_imbalance": round(imb, 3) if s["entry"]["require_ob_confirmation"] else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    # Load env
    from pathlib import Path
    for line in Path("/data/workspace/.env").read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

    cfg = load_strategy_config()
    client = OrderlyClient()

    print("=" * 70)
    print(f"Strategy: {cfg['strategy']['name']}")
    print(f"Phase: {cfg['phase']}")
    print("=" * 70)

    for sym in cfg["allowed_symbols"]:
        print(f"\n--- {sym} ---")
        signal = evaluate_signal(client, sym, cfg)
        if signal["action"] == "TRADE":
            print(f"  ✅ {signal['direction']} signal")
            print(f"     Entry:  {signal['entry']}")
            print(f"     Stop:   {signal['stop']}  (ATR={signal['atr']})")
            print(f"     Target: {signal['target']}")
            print(f"     RSI={signal['rsi']}  Funding={signal['funding_bps']}bps  OB={signal['ob_imbalance']}")
            print(f"     Range: {signal['range_low']} - {signal['range_high']} ({signal['range_width_pct']}%)")
        else:
            print(f"  ⏭️  SKIP — {signal['reason']}")
