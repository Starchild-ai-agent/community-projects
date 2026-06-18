"""
Virtual portfolio + risk management.

Tracks positions, exposure, P&L without actual execution.
Provides portfolio context to the LLM so it knows:
- Am I already long BTC? (don't double up)
- What's my total exposure? (correlation risk)
- How much can I risk on this trade? (position sizing)
- Am I in drawdown? (reduce aggression)

Research basis:
- FinPos: decouples direction from sizing decisions
- AI-Trader: "risk control determines cross-market robustness"
- LiveTradeBench: portfolio-management abstraction for multi-asset
"""

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Position:
    symbol: str
    side: str  # "long" or "short"
    entry_price: float
    size: float  # in quote currency (USDT)
    entry_time: float
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    stop: float = None    # invalidation level — exit if crossed
    target: float = None  # take-profit level — exit if crossed


@dataclass
class PortfolioState:
    balance: float  # starting virtual balance
    equity: float  # balance + unrealized P&L
    positions: dict = field(default_factory=dict)  # symbol → Position
    realized_pnl: float = 0.0
    peak_equity: float = 0.0
    drawdown: float = 0.0  # current drawdown from peak (%)
    trade_count: int = 0
    win_count: int = 0


class Portfolio:
    def __init__(
        self,
        initial_balance: float = 10000.0,
        max_position_pct: float = 0.10,     # max 10% per position
        max_total_exposure_pct: float = 0.30, # max 30% total exposure
        max_drawdown_pct: float = 0.15,      # stop trading at 15% drawdown
        max_correlated_positions: int = 2,    # max 2 correlated positions
        min_hold_seconds: int = 300,          # don't reverse within 5 minutes
        max_hold_seconds: float = 86400,      # force-close after 24h
        persist_dir: str = None,
    ):
        self.config = {
            "max_position_pct": max_position_pct,
            "max_total_exposure_pct": max_total_exposure_pct,
            "max_drawdown_pct": max_drawdown_pct,
            "max_correlated_positions": max_correlated_positions,
            "min_hold_seconds": min_hold_seconds,
            "max_hold_seconds": max_hold_seconds,
        }
        self._persist_dir = Path(persist_dir) if persist_dir else None
        self.state = PortfolioState(
            balance=initial_balance,
            equity=initial_balance,
            peak_equity=initial_balance,
        )
        if self._persist_dir:
            self._persist_dir.mkdir(parents=True, exist_ok=True)
            self._load()

    # ── Correlated asset groups ──
    CORRELATION_GROUPS = {
        "large_cap": ["BTC/USDT", "ETH/USDT"],
        "alt_l1": ["SOL/USDT", "AVAX/USDT", "ETH/USDT"],
        "meme": ["DOGE/USDT", "SHIB/USDT", "PEPE/USDT"],
        "defi": ["UNI/USDT", "AAVE/USDT", "ARB/USDT", "OP/USDT"],
    }

    def update_prices(self, prices: dict[str, float], check_exits: bool = True) -> list[dict]:
        """
        Update unrealized P&L for all positions with current prices, and
        close any position that hit its stop, target, or max hold time.
        Returns the list of closed positions. Pass check_exits=False when
        replaying historical prices (warmup) so stale data can't trigger exits.
        """
        closed = []
        now = time.time()
        for symbol, pos in list(self.state.positions.items()):
            if symbol not in prices:
                continue
            price = prices[symbol]
            if pos.side == "long":
                pos.unrealized_pnl = (price - pos.entry_price) / pos.entry_price * pos.size
                pos.unrealized_pnl_pct = (price - pos.entry_price) / pos.entry_price * 100
            else:
                pos.unrealized_pnl = (pos.entry_price - price) / pos.entry_price * pos.size
                pos.unrealized_pnl_pct = (pos.entry_price - price) / pos.entry_price * 100

            if not check_exits:
                continue

            reason = None
            if pos.stop is not None and (
                (pos.side == "long" and price <= pos.stop)
                or (pos.side == "short" and price >= pos.stop)
            ):
                reason = "stop"
            elif pos.target is not None and (
                (pos.side == "long" and price >= pos.target)
                or (pos.side == "short" and price <= pos.target)
            ):
                reason = "target"
            elif now - pos.entry_time >= self.config["max_hold_seconds"]:
                reason = "max_hold"

            if reason:
                pnl = self.close_position(symbol, price)
                closed.append({
                    "symbol": symbol,
                    "side": pos.side,
                    "reason": reason,
                    "exit_price": price,
                    "pnl": round(pnl, 2),
                })

        total_unrealized = sum(p.unrealized_pnl for p in self.state.positions.values())
        self.state.equity = self.state.balance + total_unrealized

        if self.state.equity > self.state.peak_equity:
            self.state.peak_equity = self.state.equity

        if self.state.peak_equity > 0:
            self.state.drawdown = round(
                (1 - self.state.equity / self.state.peak_equity) * 100, 2
            )

        return closed

    def check_risk(self, symbol: str, action: str, signal_strength: int) -> dict:
        """
        Run risk checks before allowing a signal through.
        Returns {"allowed": bool, "reason": str, "suggested_size": float}
        """
        # Already in a position on this symbol?
        if symbol in self.state.positions:
            existing = self.state.positions[symbol]
            if (action == "BUY" and existing.side == "long") or \
               (action == "SELL" and existing.side == "short"):
                return {
                    "allowed": False,
                    "reason": f"Already {existing.side} {symbol}",
                    "suggested_size": 0,
                }
            # Minimum hold period: don't reverse within 5 minutes
            hold_time = time.time() - existing.entry_time
            if hold_time < self.config.get("min_hold_seconds", 300):
                return {
                    "allowed": False,
                    "reason": f"Position too new ({hold_time:.0f}s < {self.config.get('min_hold_seconds', 300)}s min hold)",
                    "suggested_size": 0,
                }

        # Max drawdown breached?
        if self.state.drawdown >= self.config["max_drawdown_pct"] * 100:
            return {
                "allowed": False,
                "reason": f"Drawdown {self.state.drawdown:.1f}% exceeds max {self.config['max_drawdown_pct']*100}%",
                "suggested_size": 0,
            }

        # Total exposure check
        total_exposure = sum(p.size for p in self.state.positions.values())
        max_total = self.state.equity * self.config["max_total_exposure_pct"]
        if total_exposure >= max_total:
            return {
                "allowed": False,
                "reason": f"Total exposure ${total_exposure:.0f} at max (${max_total:.0f})",
                "suggested_size": 0,
            }

        # Correlation check
        correlated_count = 0
        for group_name, group_symbols in self.CORRELATION_GROUPS.items():
            if symbol in group_symbols:
                for s in group_symbols:
                    if s in self.state.positions and s != symbol:
                        correlated_count += 1

        if correlated_count >= self.config["max_correlated_positions"]:
            return {
                "allowed": False,
                "reason": f"Too many correlated positions ({correlated_count} already open)",
                "suggested_size": 0,
            }

        # Position sizing: scale with signal strength
        max_size = self.state.equity * self.config["max_position_pct"]
        # Strength 100 = full size, 60 = 60% of max, etc.
        strength_scalar = min(signal_strength, 100) / 100
        suggested_size = round(max_size * strength_scalar, 2)

        # Don't exceed remaining exposure budget
        remaining = max_total - total_exposure
        suggested_size = min(suggested_size, remaining)

        return {
            "allowed": True,
            "reason": "OK",
            "suggested_size": suggested_size,
        }

    def open_position(
        self,
        symbol: str,
        side: str,
        price: float,
        size: float,
        stop: float = None,
        target: float = None,
    ):
        """Record a virtual position open. Closes (realizes) any existing
        position on the symbol first so a flip can't silently drop its P&L."""
        if symbol in self.state.positions:
            pnl = self.close_position(symbol, price)
            print(f"[PORTFOLIO] Flipped {symbol}: closed prior position, "
                  f"realized ${pnl:+.2f}")

        self.state.positions[symbol] = Position(
            symbol=symbol,
            side=side,
            entry_price=price,
            size=size,
            entry_time=time.time(),
            stop=stop,
            target=target,
        )
        self.state.trade_count += 1
        self._persist()

    def close_position(self, symbol: str, price: float) -> float:
        """Close a virtual position, return realized P&L."""
        if symbol not in self.state.positions:
            return 0.0

        pos = self.state.positions.pop(symbol)
        if pos.side == "long":
            pnl = (price - pos.entry_price) / pos.entry_price * pos.size
        else:
            pnl = (pos.entry_price - price) / pos.entry_price * pos.size

        self.state.realized_pnl += pnl
        self.state.balance += pnl
        if pnl > 0:
            self.state.win_count += 1

        self._persist()
        return pnl

    def format_for_llm(self) -> str:
        """Format portfolio state for injection into LLM context."""
        s = self.state
        lines = [
            f"**Balance:** ${s.balance:.2f} | **Equity:** ${s.equity:.2f}",
            f"**Realized P&L:** ${s.realized_pnl:+.2f} | "
            f"**Drawdown:** {s.drawdown:.1f}%",
            f"**Trades:** {s.trade_count} | "
            f"**Win Rate:** {s.win_count}/{s.trade_count if s.trade_count else 1} "
            f"({s.win_count/max(s.trade_count,1)*100:.0f}%)",
        ]

        if s.positions:
            lines.append("")
            lines.append("**Open Positions:**")
            for symbol, pos in s.positions.items():
                lines.append(
                    f"- {pos.side.upper()} {symbol}: "
                    f"entry ${pos.entry_price:.2f}, "
                    f"size ${pos.size:.0f}, "
                    f"P&L {pos.unrealized_pnl_pct:+.2f}%"
                )
        else:
            lines.append("\n**No open positions.**")

        risk_note = ""
        if s.drawdown > self.config["max_drawdown_pct"] * 100 * 0.7:
            risk_note = "\n**WARNING: Approaching max drawdown limit. Reduce risk.**"

        total_exposure = sum(p.size for p in s.positions.values())
        max_exposure = s.equity * self.config["max_total_exposure_pct"]
        lines.append(
            f"\n**Exposure:** ${total_exposure:.0f} / ${max_exposure:.0f} max"
            f"{risk_note}"
        )

        return "\n".join(lines)

    def _persist(self):
        if not self._persist_dir:
            return
        data = {
            "balance": self.state.balance,
            "equity": self.state.equity,
            "realized_pnl": self.state.realized_pnl,
            "peak_equity": self.state.peak_equity,
            "drawdown": self.state.drawdown,
            "trade_count": self.state.trade_count,
            "win_count": self.state.win_count,
            "positions": {k: asdict(v) for k, v in self.state.positions.items()},
        }
        with open(self._persist_dir / "portfolio.json", "w") as f:
            json.dump(data, f, indent=2)

    def _load(self):
        if not self._persist_dir:
            return
        path = self._persist_dir / "portfolio.json"
        if not path.exists():
            return
        with open(path) as f:
            data = json.load(f)
        self.state.balance = data.get("balance", self.state.balance)
        self.state.equity = data.get("equity", self.state.equity)
        self.state.realized_pnl = data.get("realized_pnl", 0)
        self.state.peak_equity = data.get("peak_equity", self.state.peak_equity)
        self.state.drawdown = data.get("drawdown", 0)
        self.state.trade_count = data.get("trade_count", 0)
        self.state.win_count = data.get("win_count", 0)
        for symbol, pdata in data.get("positions", {}).items():
            self.state.positions[symbol] = Position(**pdata)
