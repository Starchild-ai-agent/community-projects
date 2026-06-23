# -*- task-system: v3 -*-
"""
WOOFi Pro Agent — Live execution loop.

Runs every hour via scheduled task.
1. Check circuit breakers (daily/weekly loss limits).
2. Check open positions — manage exits (stop/target/max-hold/range-break).
3. Evaluate strategy signals for allowed symbols.
4. If signal = TRADE and no existing position on that symbol:
   - Size position via risk engine.
   - Place LIMIT entry order (maker fee).
   - Place STOP-LOSS algo order (reduce-only).
   - Place TAKE-PROFIT algo order (reduce-only).
5. Log everything.
6. Push summary to user.
"""
import os, sys, json, time, uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

# --- Load env ---
for line in Path("/data/workspace/.env").read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

sys.path.insert(0, os.path.dirname(__file__))

from client import OrderlyClient
from strategy import evaluate_signal, load_strategy_config
from risk import RiskEngine, load_risk_config
from market_data import get_recent_candles

LOG_DIR = Path("/data/workspace/projects/woofi-agent/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

SIGNALS_LOG = LOG_DIR / "signals.log"
TRADES_LOG = LOG_DIR / "trades.log"
POSITIONS_LOG = LOG_DIR / "positions.log"


def log(path, entry):
    """Append a JSON line to a log file."""
    with open(path, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def push_to_user(message):
    """Send a push notification to the user via the platform push endpoint."""
    try:
        import requests
        # Thread ID for push notifications — derived from runtime session ID
        thread_id = "27370d93-8879-41f8-bef7-8034a39938ea"
        requests.post(
            "http://localhost:8000/push",
            json={
                "message": message,
                "thread_id": thread_id,
            },
            timeout=10,
        )
    except Exception:
        pass  # push is best-effort


def get_open_positions(client):
    """Return dict of symbol -> position for all open positions."""
    resp = client.get_positions()
    rows = resp.get("data", {}).get("rows", [])
    # filter to actually-open positions
    open_pos = {}
    for r in rows:
        if float(r.get("qty", 0) or 0) != 0:
            open_pos[r["symbol"]] = r
    return open_pos


def manage_open_positions(client, risk_engine, strategy_cfg):
    """Check open positions for exit conditions. Returns list of actions taken."""
    actions = []
    positions = get_open_positions(client)

    if not positions:
        return actions

    now = datetime.now(timezone.utc)

    for symbol, pos in positions.items():
        entry_price = float(pos.get("entry_price", 0))
        qty = float(pos.get("qty", 0))  # positive=long, negative=short
        side = "LONG" if qty > 0 else "SHORT"
        mark_price = float(pos.get("mark_price", 0))
        unrealized_pnl = float(pos.get("upnl", 0))
        open_time = datetime.fromtimestamp(
            int(pos.get("timestamp", 0)) / 1000, tz=timezone.utc
        )
        hold_hours = (now - open_time).total_seconds() / 3600

        # Check max hold time
        max_hold = strategy_cfg["strategy"]["exit"]["max_hold_hours"]
        if hold_hours >= max_hold:
            # Close position at market
            close_side = "SELL" if side == "LONG" else "BUY"
            close_qty = abs(qty)
            try:
                result = client.create_order(
                    symbol=symbol,
                    order_type="MARKET",
                    side=close_side,
                    order_quantity=close_qty,
                    reduce_only=True,
                )
                actions.append(f"⏰ Closed {symbol} {side} — max hold {hold_hours:.1f}h reached. PnL: ${unrealized_pnl:.2f}")
                log(TRADES_LOG, {
                    "action": "CLOSE_MAX_HOLD", "symbol": symbol, "side": side,
                    "pnl": unrealized_pnl, "hold_hours": hold_hours,
                    "result": result, "timestamp": now.isoformat(),
                })
            except Exception as e:
                actions.append(f"❌ Failed to close {symbol} (max hold): {e}")

        # Check range break — if price has moved beyond the range, exit
        candles = get_recent_candles(client, symbol, "1h",
                                     strategy_cfg["market_data"]["candle_lookback"])
        if len(candles) >= strategy_cfg["strategy"]["range_lookback"]:
            recent = candles[-strategy_cfg["strategy"]["range_lookback"]:]
            range_hi = max(c["high"] for c in recent)
            range_lo = min(c["low"] for c in recent)
            broke_range = False
            if side == "LONG" and mark_price < range_lo * 0.998:
                broke_range = True
            elif side == "SHORT" and mark_price > range_hi * 1.002:
                broke_range = True

            if broke_range:
                close_side = "SELL" if side == "LONG" else "BUY"
                try:
                    result = client.create_order(
                        symbol=symbol, order_type="MARKET",
                        side=close_side, order_quantity=abs(qty),
                        reduce_only=True,
                    )
                    actions.append(f"📉 Closed {symbol} {side} — range broken. PnL: ${unrealized_pnl:.2f}")
                    log(TRADES_LOG, {
                        "action": "CLOSE_RANGE_BREAK", "symbol": symbol, "side": side,
                        "pnl": unrealized_pnl, "mark_price": mark_price,
                        "range_hi": range_hi, "range_lo": range_lo,
                        "result": result, "timestamp": now.isoformat(),
                    })
                except Exception as e:
                    actions.append(f"❌ Failed to close {symbol} (range break): {e}")

    return actions


def execute_entry(client, risk_engine, signal, strategy_cfg):
    """Place entry + stop-loss + take-profit orders for a signal."""
    symbol = signal["symbol"]
    direction = signal["direction"]
    entry = signal["entry"]
    stop = signal["stop"]
    target = signal["target"]

    # Position size via risk engine
    size_result, reason = risk_engine.position_size(entry, stop)
    if size_result is None:
        return f"❌ {symbol}: position sizing failed — {reason}"

    qty = size_result["quantity"]
    if qty <= 0:
        return f"❌ {symbol}: quantity <= 0"

    side = "BUY" if direction == "LONG" else "SELL"
    close_side = "SELL" if direction == "LONG" else "BUY"
    client_oid = str(uuid.uuid4())[:36]

    now = datetime.now(timezone.utc).isoformat()
    actions = []

    # 1. Place LIMIT entry order (maker fee, cheaper)
    try:
        entry_result = client.create_order(
            symbol=symbol,
            order_type="LIMIT",
            side=side,
            order_price=entry,
            order_quantity=qty,
            client_order_id=f"entry_{client_oid}",
        )
        if not entry_result.get("success"):
            return f"❌ {symbol}: entry order rejected — {entry_result.get('message','?')}"
        actions.append(f"✅ Entry: {direction} {qty} {symbol} @ {entry} (LIMIT)")
        log(TRADES_LOG, {
            "action": "ENTRY", "symbol": symbol, "direction": direction,
            "entry": entry, "stop": stop, "target": target, "qty": qty,
            "risk_usd": size_result["actual_risk_usd"],
            "result": entry_result, "timestamp": now,
        })
    except Exception as e:
        return f"❌ {symbol}: entry order failed — {e}"

    # 2. Place STOP-LOSS (algo order, reduce-only, market on trigger)
    try:
        sl_result = client.create_stop_order(
            symbol=symbol,
            side=close_side,
            trigger_price=stop,
            order_type="MARKET",
            order_quantity=qty,
            reduce_only=True,
            client_order_id=f"sl_{client_oid}",
        )
        if sl_result.get("success"):
            actions.append(f"🛑 Stop-loss: {stop}")
        else:
            actions.append(f"⚠️ Stop-loss failed: {sl_result.get('message','?')}")
        log(TRADES_LOG, {
            "action": "STOP_LOSS", "symbol": symbol, "trigger": stop,
            "qty": qty, "result": sl_result, "timestamp": now,
        })
    except Exception as e:
        actions.append(f"⚠️ Stop-loss exception: {e}")

    # 3. Place TAKE-PROFIT (algo order, reduce-only, market on trigger)
    try:
        tp_result = client.create_stop_order(
            symbol=symbol,
            side=close_side,
            trigger_price=target,
            order_type="MARKET",
            order_quantity=qty,
            reduce_only=True,
            client_order_id=f"tp_{client_oid}",
        )
        if tp_result.get("success"):
            actions.append(f"🎯 Take-profit: {target}")
        else:
            actions.append(f"⚠️ Take-profit failed: {tp_result.get('message','?')}")
        log(TRADES_LOG, {
            "action": "TAKE_PROFIT", "symbol": symbol, "trigger": target,
            "qty": qty, "result": tp_result, "timestamp": now,
        })
    except Exception as e:
        actions.append(f"⚠️ Take-profit exception: {e}")

    return "\n".join(actions)


def main():
    now = datetime.now(timezone.utc)
    client = OrderlyClient()
    risk_engine = RiskEngine()
    strategy_cfg = load_strategy_config()

    # Only push to user when something actionable happens (entry, exit, halt, error)
    push_messages = []

    # 1. Check circuit breakers
    ok, reason = risk_engine.check_circuit_breakers()
    if not ok:
        push_messages.append(f"⛔ WOOFi Agent HALTED: {reason}")
        if push_messages:
            push_to_user("\n".join(push_messages))
        return

    # 2. Manage open positions first
    position_actions = manage_open_positions(client, risk_engine, strategy_cfg)
    if position_actions:
        push_messages.extend(position_actions)

    # 3. Check existing positions — don't open new on same symbol
    open_positions = get_open_positions(client)
    open_symbols = set(open_positions.keys())

    # 4. Check max concurrent positions
    max_positions = risk_engine.cfg["position_sizing"]["max_concurrent_positions"]
    if len(open_positions) >= max_positions:
        # No push — this is a normal steady-state, not actionable
        return

    # 5. Evaluate signals
    for symbol in strategy_cfg["allowed_symbols"]:
        if symbol in open_symbols:
            continue
        signal = evaluate_signal(client, symbol, strategy_cfg)
        log(SIGNALS_LOG, {**signal, "timestamp": now.isoformat()})

        if signal["action"] == "TRADE":
            # Pre-trade risk check
            approved, details = risk_engine.pre_trade_check(
                symbol, "BUY" if signal["direction"] == "LONG" else "SELL",
                signal["entry"], signal["stop"],
                funding_rate=signal["funding_bps"] / 10000,
            )
            if approved:
                entry_msg = execute_entry(client, risk_engine, signal, strategy_cfg)
                push_messages.append(f"🤖 WOOFi Agent — {now.strftime('%H:%M UTC')}\n{entry_msg}")
            else:
                log(SIGNALS_LOG, {
                    "symbol": symbol, "action": "RISK_REJECT",
                    "reason": details, "timestamp": now.isoformat(),
                })

    # 6. Push only if there are actionable messages
    if push_messages:
        full = "\n\n".join(push_messages)
        print(full)
        push_to_user(full)


if __name__ == "__main__":
    main()
