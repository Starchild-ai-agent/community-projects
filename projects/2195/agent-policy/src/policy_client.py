# -*- coding: utf-8 -*-
"""
PolicyClient — drop-in wrapper for OrderlyClient that enforces policy.

  raw    = OrderlyClient(base_url, creds)
  client = PolicyClient(raw, engine, notifier=TelegramNotifier())

Every mutating call is intercepted and evaluated.
Read-only calls pass through unchanged.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from policy import Decision, PolicyEngine, PolicyViolation, Verdict
from notifier import TelegramNotifier

log = logging.getLogger("policy.client")

class PolicyClient:
    def __init__(self, client, engine: PolicyEngine,
                 notifier: Optional[TelegramNotifier] = None,
                 dry_run: bool = False):
        self._c        = client
        self._engine   = engine
        self._notifier = notifier
        self._dry_run  = dry_run

    def _gate(self, action_type: str, body: dict = {}, extra: Dict[str, Any] = {}):
        d = self._engine.evaluate(action_type, body, extra)
        log.info("policy [%s] %s — %s", d.verdict.value, action_type, d.reason)
        if d.verdict == Verdict.ALLOW:
            return
        if d.verdict == Verdict.BLOCK:
            log.error("BLOCKED %s: %s", action_type, d.reason)
            if self._notifier:
                self._notifier.notify(f"🚫 *BLOCKED* `{action_type}`\n`{d.rule}`\n{d.reason}")
            raise PolicyViolation(d)
        # ESCALATE
        if not self._notifier:
            raise PolicyViolation(Decision(
                Verdict.BLOCK, "no notifier for ESCALATE",
                rule="policy_client/no_notifier", action=action_type, context=body))
        result = self._notifier.request_approval(d)
        if not result.approved:
            raise PolicyViolation(Decision(
                Verdict.BLOCK, f"denied by human (timeout={result.timeout})",
                rule="escalate_denied", action=action_type, context=body))

    # ── mutating — gated ─────────────────────────────────────────────────────
    def place_order(self, body: dict) -> dict:
        self._gate("place_order", body=body)
        if self._dry_run: return {"success": True, "dry_run": True}
        return self._c.place_order(body)

    def batch_orders(self, orders: List[dict]) -> dict:
        for o in orders: self._gate("place_order", body=o)
        if self._dry_run: return {"success": True, "dry_run": True}
        return self._c.batch_orders(orders)

    def cancel_all(self, symbol: str) -> dict:
        self._gate("cancel_all", body={"symbol": symbol})
        if self._dry_run: return {"success": True, "dry_run": True}
        return self._c.cancel_all(symbol)

    def cancel_order(self, order_id: int, symbol: str) -> dict:
        self._gate("cancel_order", body={"order_id": order_id, "symbol": symbol})
        if self._dry_run: return {"success": True, "dry_run": True}
        return self._c.cancel_order(order_id, symbol)

    # ── read-only — pass through ─────────────────────────────────────────────
    def positions(self):              return self._c.positions()
    def holding(self):                return self._c.holding()
    def open_orders(self, *a, **kw):  return self._c.open_orders(*a, **kw)
    def trades(self, *a, **kw):       return self._c.trades(*a, **kw)
    def orderbook(self, *a, **kw):    return self._c.orderbook(*a, **kw)
    def funding(self, *a, **kw):      return self._c.funding(*a, **kw)
    def market_trades(self, *a, **kw):return self._c.market_trades(*a, **kw)
    def futures_info(self, *a, **kw): return self._c.futures_info(*a, **kw)
    def info(self, *a, **kw):         return self._c.info(*a, **kw)
