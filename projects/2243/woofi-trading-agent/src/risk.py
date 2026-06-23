"""
Risk engine — position sizing, circuit breakers, pre-trade checks.
Reads config/risk.yaml. Does NOT place orders.
"""
import yaml
import os
from datetime import datetime, timezone

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "risk.yaml")


def load_risk_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


class RiskEngine:
    def __init__(self, config=None):
        self.cfg = config or load_risk_config()
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.consecutive_losses = 0
        self.open_positions = 0
        self.halted = False
        self.halt_reason = None

    def equity(self):
        return self.cfg["account"]["starting_balance_usd"] + self.daily_pnl

    def check_circuit_breakers(self):
        """Return (ok, reason)."""
        e = self.equity()
        if self.daily_pnl <= -self.cfg["circuit_breakers"]["max_daily_loss_usd"]:
            self.halted = True
            self.halt_reason = f"Daily loss limit hit: {self.daily_pnl:.2f} USD"
            return False, self.halt_reason
        if self.weekly_pnl <= -self.cfg["circuit_breakers"]["max_weekly_loss_usd"]:
            self.halted = True
            self.halt_reason = f"Weekly loss limit hit: {self.weekly_pnl:.2f} USD"
            return False, self.halt_reason
        if self.consecutive_losses >= self.cfg["circuit_breakers"]["max_consecutive_losses"]:
            self.halted = True
            self.halt_reason = f"Max consecutive losses: {self.consecutive_losses}"
            return False, self.halt_reason
        return True, "ok"

    def position_size(self, entry_price, stop_price, leverage=None):
        """
        Calculate position size based on risk_per_trade.
        Returns (notional_usd, quantity, margin_required, actual_risk_usd).
        """
        ok, reason = self.check_circuit_breakers()
        if not ok:
            return None, reason

        lev = leverage or self.cfg["leverage"]["default_position_leverage"]
        max_lev = self.cfg["leverage"]["max_position_leverage"]
        if lev > max_lev:
            return None, f"Leverage {lev}x exceeds max {max_lev}x"

        equity = self.equity()
        risk_usd = equity * (self.cfg["position_sizing"]["risk_per_trade_pct"] / 100)

        if entry_price == stop_price:
            return None, "entry == stop, cannot compute size"

        stop_distance_pct = abs(entry_price - stop_price) / entry_price
        # notional such that stop_distance * notional = risk_usd
        notional = risk_usd / stop_distance_pct
        margin = notional / lev
        quantity = notional / entry_price

        # cap notional
        max_notional = equity * (self.cfg["position_sizing"]["max_notional_per_position_pct"] / 100)
        if notional > max_notional:
            notional = max_notional
            quantity = notional / entry_price
            margin = notional / lev
            actual_risk = notional * stop_distance_pct
        else:
            actual_risk = risk_usd

        if self.open_positions >= self.cfg["position_sizing"]["max_concurrent_positions"]:
            return None, f"Max concurrent positions ({self.open_positions})"

        return {
            "notional_usd": round(notional, 2),
            "quantity": round(quantity, 6),
            "margin_required_usd": round(margin, 2),
            "leverage": lev,
            "actual_risk_usd": round(actual_risk, 2),
            "stop_distance_pct": round(stop_distance_pct * 100, 2),
            "entry_price": entry_price,
            "stop_price": stop_price,
        }, "ok"

    def pre_trade_check(self, symbol, side, entry, stop, funding_rate=None):
        """Full pre-trade validation. Returns (approved, details/reason)."""
        # symbol whitelist
        if symbol not in self.cfg["strategy_filters"]["allowed_symbols"]:
            return False, f"{symbol} not in allowed list"

        # funding filter
        if funding_rate is not None:
            fr_bps = funding_rate * 10000
            if side == "BUY" and fr_bps > self.cfg["strategy_filters"]["avoid_high_funding_bps"]:
                return False, f"Funding {fr_bps:.1f}bps too high for long"
            if abs(fr_bps) > self.cfg["strategy_filters"]["avoid_extreme_funding_bps"]:
                return False, f"Funding {fr_bps:.1f}bps extreme — avoid both sides"

        # R:R check (need take_profit too)
        size_result, reason = self.position_size(entry, stop)
        if size_result is None:
            return False, reason

        return True, size_result


if __name__ == "__main__":
    re = RiskEngine()
    print("=== Risk config loaded ===")
    print(f"Equity: ${re.equity():.2f}")
    print(f"Max leverage: {re.cfg['leverage']['max_account_leverage']}x")
    print(f"Risk/trade: ${re.equity() * re.cfg['position_sizing']['risk_per_trade_pct']/100:.2f}")

    print("\n=== Position size: BTC long @ 65000, stop 64000, 2x lev ===")
    result, reason = re.position_size(65000, 64000, leverage=2)
    print(reason, result)

    print("\n=== Pre-trade check: BTC long with 0.01% funding ===")
    ok, details = re.pre_trade_check("PERP_BTC_USDC", "BUY", 65000, 64000, funding_rate=0.0001)
    print(ok, details)

    print("\n=== Pre-trade check: BTC long with 0.04% funding (too high) ===")
    ok, details = re.pre_trade_check("PERP_BTC_USDC", "BUY", 65000, 64000, funding_rate=0.0004)
    print(ok, details)

    print("\n=== Pre-trade check: disallowed symbol ===")
    ok, details = re.pre_trade_check("PERP_DOGE_USDC", "BUY", 0.2, 0.19)
    print(ok, details)
