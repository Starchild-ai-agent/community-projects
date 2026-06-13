# -*- coding: utf-8 -*-
"""Unit tests — no Telegram, no exchange calls."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from policy import PolicyEngine, Verdict, PolicyViolation

CFG = {
    "assets": {"allowed": ["NATGAS"], "max_notional_per_asset": 65000},
    "actions": {
        "autonomous": [
            {"type": "place_order", "condition": "notional <= 65000"},
            {"type": "cancel_order"},
        ],
        "escalate": [
            {"type": "place_order", "condition": "notional > 65000"},
            {"type": "close_position"},
        ],
        "forbidden": [
            {"type": "withdraw"},
            {"type": "cancel_all"},
            {"type": "change_leverage"},
        ],
    },
    "circuit_breakers": {
        "daily_loss_limit": 1000,
        "drawdown_pct": 5.0,
        "consecutive_loss_trades": 8,
        "margin_ratio_max": 65,
    },
}

def e(): return PolicyEngine.from_dict(CFG)

def test_normal_order_allow():
    d = e().evaluate("place_order", {"symbol": "PERP_NATGAS_USDC", "price": 3.15, "quantity": 640})
    assert d.verdict == Verdict.ALLOW, d

def test_oversized_order_escalate():
    d = e().evaluate("place_order", {"symbol": "PERP_NATGAS_USDC", "price": 3.15, "quantity": 25000})
    assert d.verdict == Verdict.ESCALATE, d

def test_cancel_order_allow():
    d = e().evaluate("cancel_order", {"order_id": 123, "symbol": "PERP_NATGAS_USDC"})
    assert d.verdict == Verdict.ALLOW, d

def test_cancel_all_block():
    d = e().evaluate("cancel_all", {"symbol": "PERP_NATGAS_USDC"})
    assert d.verdict == Verdict.BLOCK, d

def test_withdraw_block():
    d = e().evaluate("withdraw", {})
    assert d.verdict == Verdict.BLOCK, d

def test_wrong_asset_block():
    d = e().evaluate("place_order", {"symbol": "PERP_BTC_USDC", "price": 60000, "quantity": 1})
    assert d.verdict == Verdict.BLOCK, d

def test_close_position_escalate():
    d = e().evaluate("close_position", {})
    assert d.verdict == Verdict.ESCALATE, d

def test_unknown_action_escalate():
    d = e().evaluate("wiggle_the_knobs", {})
    assert d.verdict == Verdict.ESCALATE, d

def test_circuit_breaker_daily_loss():
    eng = e()
    eng.breakers.daily_realized = -1001.0
    d = eng.evaluate("place_order", {"symbol": "PERP_NATGAS_USDC", "price": 3.15, "quantity": 100})
    assert d.verdict == Verdict.BLOCK
    assert "daily_loss" in d.reason or "daily" in d.reason.lower()

def test_circuit_breaker_margin():
    eng = e()
    eng.breakers.margin_ratio = 70.0
    d = eng.evaluate("place_order", {"symbol": "PERP_NATGAS_USDC", "price": 3.15, "quantity": 100})
    assert d.verdict == Verdict.BLOCK

def test_circuit_breaker_consec_losses():
    eng = e()
    eng.breakers.consec_losses = 9
    d = eng.evaluate("place_order", {"symbol": "PERP_NATGAS_USDC", "price": 3.15, "quantity": 100})
    assert d.verdict == Verdict.BLOCK

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t(); print(f"  ✓ {t.__name__}"); passed += 1
        except Exception as ex:
            print(f"  ✗ {t.__name__}: {ex}"); failed += 1
    print(f"\n{passed} passed, {failed} failed")
