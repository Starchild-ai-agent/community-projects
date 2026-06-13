# -*- coding: utf-8 -*-
"""
agent-policy — signing policy engine for AI-driven DeFi bots.

Every action an agent proposes goes through PolicyEngine.evaluate() BEFORE
any key is touched.  Returns one of three verdicts:

  ALLOW     → execute immediately, no human needed
  ESCALATE  → push to Telegram, wait for approval, then execute or abort
  BLOCK     → hard-blocked, raise PolicyViolation, never execute
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
    _YAML = True
except ImportError:
    _YAML = False

log = logging.getLogger("policy")


# ── Verdict ───────────────────────────────────────────────────────────────────

class Verdict(str, Enum):
    ALLOW    = "ALLOW"
    ESCALATE = "ESCALATE"
    BLOCK    = "BLOCK"


@dataclass
class Decision:
    verdict: Verdict
    reason:  str
    rule:    Optional[str]       = None
    action:  Optional[str]       = None
    context: Dict[str, Any]      = field(default_factory=dict)


class PolicyViolation(RuntimeError):
    def __init__(self, decision: Decision):
        super().__init__(f"BLOCKED [{decision.rule}]: {decision.reason}")
        self.decision = decision


# ── Circuit Breakers ──────────────────────────────────────────────────────────

class CircuitBreakers:
    def __init__(self, cfg: dict, state_path: Optional[Path] = None):
        self.daily_loss_limit   = float(cfg.get("daily_loss_limit", 9999))
        self.drawdown_pct       = float(cfg.get("drawdown_pct", 100))
        self.consec_loss_trades = int(cfg.get("consecutive_loss_trades", 9999))
        self.margin_ratio_max   = float(cfg.get("margin_ratio_max", 99))
        self.state_path         = state_path
        self._lock              = threading.Lock()
        self.daily_realized     = 0.0
        self.peak_equity        = 0.0
        self.current_equity     = 0.0
        self.consec_losses      = 0
        self.margin_ratio       = 0.0
        self.tripped: Dict[str, bool] = {}
        if state_path and Path(state_path).exists():
            self._load()

    def _load(self):
        try:
            s = json.loads(Path(self.state_path).read_text())
            self.daily_realized = s.get("daily_realized", 0.0)
            self.peak_equity    = s.get("peak_equity", 0.0)
            self.current_equity = s.get("current_equity", 0.0)
            self.consec_losses  = s.get("consec_losses", 0)
            self.margin_ratio   = s.get("margin_ratio", 0.0)
            self.tripped        = s.get("tripped", {})
        except Exception as e:
            log.warning("circuit breaker state load failed: %s", e)

    def _save(self):
        if not self.state_path:
            return
        try:
            Path(self.state_path).write_text(json.dumps({
                "daily_realized": self.daily_realized,
                "peak_equity":    self.peak_equity,
                "current_equity": self.current_equity,
                "consec_losses":  self.consec_losses,
                "margin_ratio":   self.margin_ratio,
                "tripped":        self.tripped,
                "ts":             time.time(),
            }))
        except Exception as e:
            log.warning("circuit breaker state save failed: %s", e)

    def update(self, realized_pnl: float = 0.0, equity: Optional[float] = None,
               margin_ratio: Optional[float] = None, trade_pnl: Optional[float] = None):
        with self._lock:
            self.daily_realized += realized_pnl
            if equity is not None:
                self.current_equity = equity
                if equity > self.peak_equity:
                    self.peak_equity = equity
            if margin_ratio is not None:
                self.margin_ratio = margin_ratio
            if trade_pnl is not None:
                self.consec_losses = self.consec_losses + 1 if trade_pnl < 0 else 0
            self._save()

    def check(self) -> Optional[Decision]:
        with self._lock:
            if self.daily_realized <= -abs(self.daily_loss_limit):
                self.tripped["daily_loss"] = True; self._save()
                return Decision(Verdict.BLOCK,
                    f"daily realized PnL {self.daily_realized:.2f} breached limit "
                    f"-{self.daily_loss_limit:.2f}", rule="circuit_breaker/daily_loss")
            dd = 0.0
            if self.peak_equity > 0:
                dd = (self.peak_equity - self.current_equity) / self.peak_equity * 100
            if dd >= self.drawdown_pct:
                self.tripped["drawdown"] = True; self._save()
                return Decision(Verdict.BLOCK,
                    f"drawdown {dd:.1f}% >= limit {self.drawdown_pct}%",
                    rule="circuit_breaker/drawdown")
            if self.consec_losses >= self.consec_loss_trades:
                self.tripped["consec_losses"] = True; self._save()
                return Decision(Verdict.BLOCK,
                    f"{self.consec_losses} consecutive losing trades >= limit {self.consec_loss_trades}",
                    rule="circuit_breaker/consec_losses")
            if self.margin_ratio >= self.margin_ratio_max:
                self.tripped["margin_ratio"] = True; self._save()
                return Decision(Verdict.BLOCK,
                    f"margin ratio {self.margin_ratio:.1f}% >= limit {self.margin_ratio_max}%",
                    rule="circuit_breaker/margin_ratio")
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _eval_condition(cond: Optional[str], ctx: Dict[str, Any]) -> bool:
    if not cond:
        return True
    try:
        return bool(eval(cond, {"__builtins__": {}}, ctx))
    except Exception as e:
        log.warning("condition eval error '%s': %s — treating as True", cond, e)
        return True

def _notional(body: dict) -> float:
    price = float(body.get("price", 0) or 0)
    qty   = float(body.get("quantity", body.get("qty", 0)) or 0)
    return price * qty


# ── PolicyEngine ──────────────────────────────────────────────────────────────

class PolicyEngine:
    """
    Evaluate a proposed action against a YAML policy.

    Policy YAML schema:

      assets:
        allowed: [NATGAS, BTC]
        max_notional_per_asset: 65000

      actions:
        autonomous:           # ALLOW
          - type: place_order
            condition: "notional <= 65000"
          - type: cancel_order
        escalate:             # push to human
          - type: place_order
            condition: "notional > 65000"
          - type: close_position
        forbidden:            # hard BLOCK
          - type: withdraw
          - type: cancel_all

      circuit_breakers:
        daily_loss_limit: 1000
        drawdown_pct: 5.0
        consecutive_loss_trades: 8
        margin_ratio_max: 65

    Unmatched action → ESCALATE (fail-safe default).
    """

    def __init__(self, cfg: dict, state_path: Optional[Path] = None):
        self._cfg     = cfg
        self._assets  = cfg.get("assets", {})
        self._actions = cfg.get("actions", {})
        self.breakers = CircuitBreakers(cfg.get("circuit_breakers", {}), state_path)

    @classmethod
    def from_yaml(cls, path, state_path=None):
        if not _YAML:
            raise ImportError("pyyaml not installed — pip install pyyaml")
        raw = yaml.safe_load(Path(path).read_text())
        return cls(raw, state_path)

    @classmethod
    def from_dict(cls, cfg: dict, state_path=None):
        return cls(cfg, state_path)

    def evaluate(self, action_type: str, body: dict = {},
                 extra: Dict[str, Any] = {}) -> Decision:
        # 1 — circuit breakers (highest priority)
        cb = self.breakers.check()
        if cb:
            cb.action = action_type; cb.context = body
            return cb

        # 2 — build eval context
        ctx = {
            "notional": _notional(body),
            "side":     (body.get("side") or "").upper(),
            "symbol":   body.get("symbol", ""),
            "price":    float(body.get("price", 0) or 0),
            "qty":      float(body.get("quantity", body.get("qty", 0)) or 0),
            "leverage": float(body.get("leverage", 0) or 0),
            **extra,
        }

        # 3 — asset allowlist
        allowed = self._assets.get("allowed", [])
        if allowed:
            sym  = ctx["symbol"]
            coin = sym.split("_")[1] if "_" in sym else sym
            if coin and coin not in allowed:
                return Decision(Verdict.BLOCK,
                    f"asset '{coin}' not in allowed list {allowed}",
                    rule="asset_allowlist", action=action_type, context=body)

        # 4 — per-asset notional cap → escalate
        max_not = self._assets.get("max_notional_per_asset")
        if max_not and ctx["notional"] > float(max_not):
            return Decision(Verdict.ESCALATE,
                f"notional {ctx['notional']:.0f} > max_notional_per_asset {max_not}",
                rule="max_notional_per_asset", action=action_type, context=body)

        # 5 — match action rules (forbidden wins, then autonomous, then escalate)
        for rule_type, verdict in [
            ("forbidden",  Verdict.BLOCK),
            ("autonomous", Verdict.ALLOW),
            ("escalate",   Verdict.ESCALATE),
        ]:
            for rule in self._actions.get(rule_type, []):
                if rule.get("type") != action_type:
                    continue
                if _eval_condition(rule.get("condition"), ctx):
                    return Decision(verdict,
                        f"matched {rule_type} rule: {rule}",
                        rule=f"{rule_type}/{action_type}",
                        action=action_type, context=body)

        # 6 — default: fail-safe escalate
        return Decision(Verdict.ESCALATE,
            f"no rule matched '{action_type}' — escalating by default (fail-safe)",
            rule="default_escalate", action=action_type, context=body)
