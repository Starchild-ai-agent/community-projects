"""
Outcome tracker — the recursive self-improvement core.

Records price at signal time, then checks price after N candles.
Scores signals as correct/incorrect. Feeds results back into memory
as reflections so the system learns from its own outputs.

This is the Anthropic RSI paper's loop applied to trading:
  System generates signal → outcome measured → reflection stored
  → reflection injected into future analyses → better signals
  → better outcomes → better reflections → ...

Research basis:
- FinAgent: dual-level reflection (immediate + periodic review)
- LLM_trader: post-trade performance analysis + confidence recalibration
- FreqAI: continuous model retraining from new outcome data
"""

import json
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

from . import config
from .memory import AnalysisMemory


def parse_price_level(value, reference: float = None) -> float | None:
    """
    Extract a numeric price level from LLM output like
    "close below 104,500" or "4h candle under $3,950".

    With a reference price, ignores numbers more than 50% away from it
    (filters out things like "4h" or "RSI above 70") and returns the
    candidate closest to the reference.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    candidates = []
    # Numbers not embedded in words ("4h", "RSI14") and not percentages
    for m in re.finditer(r"(?<![\w.])(\d[\d,]*\.?\d*)(?![\w%])", str(value)):
        try:
            candidates.append(float(m.group(1).replace(",", "")))
        except ValueError:
            continue

    if reference:
        candidates = [c for c in candidates if abs(c - reference) / reference <= 0.5]
        if candidates:
            return min(candidates, key=lambda c: abs(c - reference))
        return None
    return candidates[0] if candidates else None


@dataclass
class PendingOutcome:
    signal_id: str
    symbol: str
    timeframe: str
    action: str  # BUY or SELL
    entry_price: float
    signal_strength: int
    bull_conviction: int
    bear_conviction: int
    invalidation: str
    timestamp: float
    checkpoints: dict = field(default_factory=dict)  # "1h": price, "4h": price, ...
    resolved: bool = False
    # Which checkpoint labels apply to this signal (scaled to its timeframe)
    horizons: list = field(default_factory=list)
    # Invalidation parsed to a price level (None if unparseable)
    inv_price: float = None


@dataclass
class OutcomeResult:
    signal_id: str
    symbol: str
    action: str
    entry_price: float
    signal_strength: int
    prices: dict  # {"1h": 105200, "4h": 104800, "24h": 106300}
    returns: dict  # {"1h": 0.38, "4h": -0.19, "24h": 1.43}  (percent)
    correct: bool  # was direction right at majority of checkpoints?
    best_return: float
    worst_return: float
    hit_invalidation: bool
    timestamp: float


# Check outcome at these intervals (seconds after signal)
CHECKPOINT_INTERVALS = {
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "24h": 86400,
}

# A signal is judged on horizons proportional to the timeframe it came from —
# a 1m scalp shouldn't be scored at 24h, a 4h swing shouldn't be scored at 15m.
TIMEFRAME_HORIZONS = {
    "1m": ["15m", "1h"],
    "5m": ["15m", "1h", "4h"],
    "15m": ["1h", "4h"],
    "30m": ["1h", "4h", "24h"],
    "1h": ["4h", "24h"],
    "4h": ["24h"],
    "1d": ["24h"],
}
DEFAULT_HORIZONS = ["1h", "4h", "24h"]


class OutcomeTracker:
    def __init__(self, memory: AnalysisMemory, persist_dir: str = None):
        self.memory = memory
        self.pending: list[PendingOutcome] = []
        self.results: list[OutcomeResult] = []
        self._signal_counter = 0
        # Optional hook fired with each resolved OutcomeResult (dashboard etc.)
        self.on_outcome = None
        # Running stats for self-tuning (must be before _load)
        self.stats = {
            "total_signals": 0,
            "correct": 0,
            "incorrect": 0,
            "avg_return_15m": 0.0,
            "avg_return_1h": 0.0,
            "avg_return_4h": 0.0,
            "avg_return_24h": 0.0,
            # Per-label sample counts so running means stay correctly weighted
            "n_15m": 0,
            "n_1h": 0,
            "n_4h": 0,
            "n_24h": 0,
            "win_rate": 0.0,
            "avg_strength_correct": 0.0,
            "avg_strength_incorrect": 0.0,
        }

        self._persist_dir = Path(persist_dir) if persist_dir else None
        if self._persist_dir:
            self._persist_dir.mkdir(parents=True, exist_ok=True)
            self._load()

    def record_signal(self, symbol: str, timeframe: str, analysis: dict, current_price: float):
        """Called when Tier 3 emits a signal. Starts tracking the outcome."""
        self._signal_counter += 1
        signal_id = f"sig_{int(time.time())}_{self._signal_counter}"

        action = analysis.get("action", "HOLD")
        invalidation = str(analysis.get("invalidation", ""))
        inv_price = parse_price_level(invalidation, reference=current_price)
        # Invalidation must be on the losing side of the entry
        if inv_price is not None:
            if (action == "BUY" and inv_price >= current_price) or \
               (action == "SELL" and inv_price <= current_price):
                inv_price = None

        pending = PendingOutcome(
            signal_id=signal_id,
            symbol=symbol,
            timeframe=timeframe,
            action=action,
            entry_price=current_price,
            signal_strength=analysis.get("signal_strength", 0),
            bull_conviction=analysis.get("bull_conviction", 0),
            bear_conviction=analysis.get("bear_conviction", 0),
            invalidation=invalidation,
            timestamp=time.time(),
            horizons=list(TIMEFRAME_HORIZONS.get(timeframe, DEFAULT_HORIZONS)),
            inv_price=inv_price,
        )
        self.pending.append(pending)
        self._persist()

    def check_outcomes(self, symbol: str, current_price: float):
        """
        Called periodically (on each candle). Checks if any pending signals
        have reached their checkpoint intervals.
        """
        now = time.time()
        newly_resolved = []

        for pending in self.pending:
            if pending.resolved or pending.symbol != symbol:
                continue

            elapsed = now - pending.timestamp
            labels = pending.horizons or DEFAULT_HORIZONS

            # Fill in checkpoints as they're reached. Only fill within a grace
            # window past the target time — after downtime, a 6h-later price
            # must not masquerade as the "15m" checkpoint.
            for label in labels:
                seconds = CHECKPOINT_INTERVALS[label]
                grace = max(300, int(seconds * 0.25))
                if label not in pending.checkpoints and \
                        seconds <= elapsed <= seconds + grace:
                    pending.checkpoints[label] = current_price

            # Check invalidation (price level parsed at record time)
            hit_invalidation = False
            if pending.inv_price is not None:
                if pending.action == "BUY" and current_price < pending.inv_price:
                    hit_invalidation = True
                elif pending.action == "SELL" and current_price > pending.inv_price:
                    hit_invalidation = True

            # Resolve when this signal's checkpoints are filled or its
            # longest horizon has passed
            all_filled = all(label in pending.checkpoints for label in labels)
            max_horizon = max(CHECKPOINT_INTERVALS[label] for label in labels)
            expired = elapsed > max_horizon + max(300, int(max_horizon * 0.25))

            if all_filled or expired or hit_invalidation:
                result = self._resolve(pending, hit_invalidation)
                pending.resolved = True
                if result is None:
                    print(f"[OUTCOME] {pending.signal_id} discarded — "
                          f"no checkpoints captured (downtime?)")
                else:
                    newly_resolved.append(result)

        # Process resolved outcomes
        for result in newly_resolved:
            self.results.append(result)
            self._update_stats(result)
            self._generate_reflection(result)
            if self.on_outcome:
                try:
                    self.on_outcome(result)
                except Exception as e:
                    print(f"[OUTCOME] on_outcome hook error: {e}")

        # Keep memory bounded
        if len(self.results) > 200:
            self.results = self.results[-200:]

        # Clean up resolved
        had_resolved = any(p.resolved for p in self.pending)
        self.pending = [p for p in self.pending if not p.resolved]
        if had_resolved:
            self._persist(new_results=newly_resolved)

    def _resolve(self, pending: PendingOutcome, hit_invalidation: bool) -> OutcomeResult | None:
        prices = dict(pending.checkpoints)
        returns = {}
        for label, price in prices.items():
            if pending.action == "BUY":
                ret = ((price - pending.entry_price) / pending.entry_price) * 100
            else:  # SELL
                ret = ((pending.entry_price - price) / pending.entry_price) * 100
            returns[label] = round(ret, 3)

        # No data and no invalidation hit → nothing to score
        if not returns and not hit_invalidation:
            return None

        # Correct if winning checkpoints outnumber losing ones. Moves inside
        # the fee/noise threshold count as neither (a +0.01% drift isn't a win).
        threshold = config.WIN_THRESHOLD_PCT
        wins = sum(1 for r in returns.values() if r > threshold)
        losses = sum(1 for r in returns.values() if r < -threshold)
        correct = wins > losses and not hit_invalidation

        return OutcomeResult(
            signal_id=pending.signal_id,
            symbol=pending.symbol,
            action=pending.action,
            entry_price=pending.entry_price,
            signal_strength=pending.signal_strength,
            prices=prices,
            returns=returns,
            correct=correct,
            best_return=max(returns.values()) if returns else 0,
            worst_return=min(returns.values()) if returns else 0,
            hit_invalidation=hit_invalidation,
            timestamp=pending.timestamp,
        )

    def _update_stats(self, result: OutcomeResult):
        self.stats["total_signals"] += 1
        if result.correct:
            self.stats["correct"] += 1
        else:
            self.stats["incorrect"] += 1

        total = self.stats["total_signals"]
        self.stats["win_rate"] = round(self.stats["correct"] / total * 100, 1)

        # Running averages, weighted per label (not every result has every label)
        for label in ["15m", "1h", "4h", "24h"]:
            if label in result.returns:
                n = self.stats.get(f"n_{label}", 0) + 1
                self.stats[f"n_{label}"] = n
                key = f"avg_return_{label}"
                old = self.stats.get(key, 0.0)
                self.stats[key] = round(old + (result.returns[label] - old) / n, 3)

        # Track strength correlation
        if result.correct:
            n = self.stats["correct"]
            old = self.stats["avg_strength_correct"]
            self.stats["avg_strength_correct"] = round(
                old + (result.signal_strength - old) / n, 1
            )
        else:
            n = self.stats["incorrect"]
            old = self.stats["avg_strength_incorrect"]
            self.stats["avg_strength_incorrect"] = round(
                old + (result.signal_strength - old) / n, 1
            )

    def _generate_reflection(self, result: OutcomeResult):
        """
        The recursive self-improvement step.
        Turns outcomes into reflections that feed back into future analyses.
        """
        ret_1h = result.returns.get("1h", "?")
        ret_4h = result.returns.get("4h", "?")
        ret_24h = result.returns.get("24h", "?")
        verdict = "CORRECT" if result.correct else "WRONG"

        if result.hit_invalidation:
            reflection = (
                f"{result.symbol} {result.action} at {result.entry_price:.2f} "
                f"(strength {result.signal_strength}) — HIT INVALIDATION. "
                f"Returns: 1h={ret_1h}%, 4h={ret_4h}%, 24h={ret_24h}%. "
                f"Invalidation level was accurate — thesis correctly identified as wrong."
            )
        elif result.correct:
            reflection = (
                f"{result.symbol} {result.action} at {result.entry_price:.2f} "
                f"(strength {result.signal_strength}) — {verdict}. "
                f"Returns: 1h={ret_1h}%, 4h={ret_4h}%, 24h={ret_24h}%. "
                f"Best: {result.best_return}%. Signal was reliable."
            )
        else:
            reflection = (
                f"{result.symbol} {result.action} at {result.entry_price:.2f} "
                f"(strength {result.signal_strength}) — {verdict}. "
                f"Returns: 1h={ret_1h}%, 4h={ret_4h}%, 24h={ret_24h}%. "
                f"Worst: {result.worst_return}%. Review: was strength too high? "
                f"Was the regime misread?"
            )

        self.memory.add_reflection(result.symbol, reflection)
        print(f"[OUTCOME] {verdict}: {reflection}")

    def get_stats_summary(self) -> str:
        s = self.stats
        if s["total_signals"] == 0:
            return "No signals tracked yet."
        return (
            f"Signals: {s['total_signals']} | Win rate: {s['win_rate']}% | "
            f"Avg returns — 1h: {s['avg_return_1h']}%, 4h: {s['avg_return_4h']}%, "
            f"24h: {s['avg_return_24h']}% | "
            f"Avg strength correct: {s['avg_strength_correct']} vs "
            f"incorrect: {s['avg_strength_incorrect']}"
        )

    def _persist(self, new_results: list = ()):
        if not self._persist_dir:
            return
        with open(self._persist_dir / "pending.json", "w") as f:
            json.dump([asdict(p) for p in self.pending], f)
        if new_results:
            # Append only newly resolved results — never re-append old ones
            with open(self._persist_dir / "results.jsonl", "a") as f:
                for r in new_results:
                    f.write(json.dumps(asdict(r)) + "\n")
        with open(self._persist_dir / "stats.json", "w") as f:
            json.dump(self.stats, f)

    def _load(self):
        if not self._persist_dir:
            return
        pending_path = self._persist_dir / "pending.json"
        if pending_path.exists():
            with open(pending_path) as f:
                data = json.load(f)
                self.pending = [PendingOutcome(**d) for d in data]

        stats_path = self._persist_dir / "stats.json"
        if stats_path.exists():
            with open(stats_path) as f:
                self.stats.update(json.load(f))
