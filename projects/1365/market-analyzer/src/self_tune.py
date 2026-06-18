"""
Self-tuning system — recursive self-improvement applied to trading.

Periodically reviews signal outcomes and adjusts system parameters:
- Tier 1 screening threshold (too many false positives → raise it)
- Analysis cooldown (too many calls → increase, too few → decrease)
- Confidence calibration (if high-strength signals are wrong, recalibrate)

This is the Anthropic recursive self-improvement loop:
  System generates signals → outcomes measured → system evaluates itself
  → adjusts its own parameters → generates better signals → ...

The key insight from the paper: "AI systems developing genuine research taste
and autonomous direction-setting capabilities." This module is the system
developing its own "trading taste" by learning what works.
"""

import json
import time
from pathlib import Path

from . import config
from .outcomes import OutcomeTracker
from .memory import AnalysisMemory


class SelfTuner:
    def __init__(
        self,
        outcomes: OutcomeTracker,
        memory: AnalysisMemory,
        review_interval: int = 3600,  # review every hour
        min_signals_for_tuning: int = 10,
        persist_dir: str = None,
    ):
        self.outcomes = outcomes
        self.memory = memory
        self.review_interval = review_interval
        self.min_signals = min_signals_for_tuning
        self._last_review = 0
        self._persist_dir = Path(persist_dir) if persist_dir else None
        self.adjustments_log: list[dict] = []
        # Optional hook fired with each review's adjustments (dashboard etc.)
        self.on_adjustments = None
        if self._persist_dir:
            self._load()

    def maybe_review(self):
        """Called periodically. Runs self-review if enough time has passed."""
        now = time.time()
        if now - self._last_review < self.review_interval:
            return
        if self.outcomes.stats["total_signals"] < self.min_signals:
            return

        self._last_review = now
        self._run_review()

    def _run_review(self):
        stats = self.outcomes.stats
        total = stats["total_signals"]
        win_rate = stats["win_rate"]
        avg_strength_correct = stats["avg_strength_correct"]
        avg_strength_incorrect = stats["avg_strength_incorrect"]

        print(f"\n[SELF-TUNE] Reviewing {total} signals (win rate: {win_rate}%)")

        adjustments = []

        # ── 1. Screen threshold adjustment ──
        # If win rate is low, we're letting too many bad setups through → raise threshold
        # If win rate is very high, we might be too conservative → lower threshold
        current_threshold = config.SCREEN_THRESHOLD
        if win_rate < 40 and total >= 15:
            new_threshold = min(current_threshold + 0.05, 0.9)
            if new_threshold != current_threshold:
                config.SCREEN_THRESHOLD = new_threshold
                adjustments.append({
                    "param": "SCREEN_THRESHOLD",
                    "old": current_threshold,
                    "new": new_threshold,
                    "reason": f"Win rate {win_rate}% too low — raising filter",
                })
        elif win_rate > 70 and total >= 15:
            new_threshold = max(current_threshold - 0.05, 0.3)
            if new_threshold != current_threshold:
                config.SCREEN_THRESHOLD = new_threshold
                adjustments.append({
                    "param": "SCREEN_THRESHOLD",
                    "old": current_threshold,
                    "new": new_threshold,
                    "reason": f"Win rate {win_rate}% strong — lowering filter to catch more setups",
                })

        # ── 2. Confidence calibration check ──
        # If high-strength signals are frequently wrong, the model is overconfident
        if avg_strength_incorrect > 60 and total >= 10:
            reflection = (
                f"CALIBRATION WARNING: Average strength of WRONG signals is "
                f"{avg_strength_incorrect:.0f}/100. The model is overconfident. "
                f"Correct signals average {avg_strength_correct:.0f}/100. "
                f"Treat signal_strength > 70 with skepticism until calibration improves."
            )
            self.memory.add_reflection("SYSTEM", reflection)
            adjustments.append({
                "param": "CONFIDENCE_CALIBRATION",
                "old": "uncalibrated",
                "new": "warning_injected",
                "reason": reflection,
            })

        # ── 3. Cooldown adjustment ──
        # If we're making too many losing trades in succession, slow down
        recent_results = self.outcomes.results[-10:]
        if len(recent_results) >= 5:
            recent_losses = sum(1 for r in recent_results if not r.correct)
            if recent_losses >= 4:  # 4+ losses in last 5
                old_cooldown = config.ANALYSIS_COOLDOWN
                new_cooldown = min(old_cooldown + 30, 300)
                if new_cooldown != old_cooldown:
                    config.ANALYSIS_COOLDOWN = new_cooldown
                    adjustments.append({
                        "param": "ANALYSIS_COOLDOWN",
                        "old": old_cooldown,
                        "new": new_cooldown,
                        "reason": f"{recent_losses}/5 recent signals wrong — slowing down",
                    })
            elif recent_losses <= 1:  # 4+ wins in last 5
                old_cooldown = config.ANALYSIS_COOLDOWN
                new_cooldown = max(old_cooldown - 15, 30)
                if new_cooldown != old_cooldown:
                    config.ANALYSIS_COOLDOWN = new_cooldown
                    adjustments.append({
                        "param": "ANALYSIS_COOLDOWN",
                        "old": old_cooldown,
                        "new": new_cooldown,
                        "reason": f"Only {recent_losses}/5 recent losses — can trade faster",
                    })

        # ── 4. Return quality check ──
        avg_1h = stats["avg_return_1h"]
        avg_4h = stats["avg_return_4h"]
        if avg_1h < -0.5 and avg_4h < -0.5 and total >= 10:
            reflection = (
                f"PERFORMANCE WARNING: Average returns are negative across timeframes "
                f"(1h: {avg_1h}%, 4h: {avg_4h}%). The system may be systematically "
                f"misreading current market conditions. Consider: is the regime detection "
                f"correct? Are we fighting the trend?"
            )
            self.memory.add_reflection("SYSTEM", reflection)
            adjustments.append({
                "param": "PERFORMANCE_CHECK",
                "old": "active",
                "new": "warning_injected",
                "reason": reflection,
            })

        # Log and persist
        if adjustments:
            for adj in adjustments:
                print(f"[SELF-TUNE] {adj['param']}: {adj['old']} → {adj['new']}")
                print(f"           Reason: {adj['reason']}")
                self.adjustments_log.append({
                    "timestamp": time.time(),
                    **adj,
                })
            self._persist()
            if self.on_adjustments:
                try:
                    self.on_adjustments(adjustments)
                except Exception as e:
                    print(f"[SELF-TUNE] on_adjustments hook error: {e}")
        else:
            print(f"[SELF-TUNE] No adjustments needed. System performing within bounds.")

    def get_summary(self) -> str:
        if not self.adjustments_log:
            return "No self-tuning adjustments yet."
        recent = self.adjustments_log[-5:]
        lines = []
        for adj in recent:
            ts = time.strftime("%m-%d %H:%M", time.gmtime(adj["timestamp"]))
            lines.append(f"- {ts}: {adj['param']} {adj['old']}→{adj['new']} ({adj['reason'][:80]})")
        return "\n".join(lines)

    def _persist(self):
        if not self._persist_dir:
            return
        data = {
            "adjustments": self.adjustments_log[-50:],
            # Tuned values must survive restarts or the "learning" resets
            "tuned": {
                "SCREEN_THRESHOLD": config.SCREEN_THRESHOLD,
                "ANALYSIS_COOLDOWN": config.ANALYSIS_COOLDOWN,
            },
        }
        with open(self._persist_dir / "self_tune.json", "w") as f:
            json.dump(data, f, indent=2)

    def _load(self):
        if not self._persist_dir:
            return
        path = self._persist_dir / "self_tune.json"
        if not path.exists():
            return
        with open(path) as f:
            data = json.load(f)

        if isinstance(data, list):  # legacy format: bare adjustments list
            self.adjustments_log = data
            return

        self.adjustments_log = data.get("adjustments", [])
        tuned = data.get("tuned", {})
        threshold = tuned.get("SCREEN_THRESHOLD")
        if threshold is not None:
            config.SCREEN_THRESHOLD = min(max(float(threshold), 0.3), 0.9)
            print(f"[SELF-TUNE] Restored SCREEN_THRESHOLD={config.SCREEN_THRESHOLD}")
        cooldown = tuned.get("ANALYSIS_COOLDOWN")
        if cooldown is not None:
            config.ANALYSIS_COOLDOWN = min(max(int(cooldown), 30), 300)
            print(f"[SELF-TUNE] Restored ANALYSIS_COOLDOWN={config.ANALYSIS_COOLDOWN}")
