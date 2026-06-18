"""
Dual-level analysis memory (FinAgent pattern):
- Recent: working memory of last N analyses for context injection
- Reflections: long-term patterns of what worked/failed
"""

import json
import time
from collections import deque
from pathlib import Path


class AnalysisMemory:
    def __init__(self, persist_dir: str = None):
        self.recent = deque(maxlen=100)
        self.reflections: list[dict] = []
        self._persist_dir = Path(persist_dir) if persist_dir else None
        if self._persist_dir:
            self._persist_dir.mkdir(parents=True, exist_ok=True)
            self._load()

    def store(self, symbol: str, timeframe: str, analysis: dict):
        entry = {
            "timestamp": time.time(),
            "symbol": symbol,
            "timeframe": timeframe,
            "action": analysis.get("action", "HOLD"),
            "signal_strength": analysis.get("signal_strength", 0),
            "trend": analysis.get("trend", "unknown"),
            "pattern": analysis.get("pattern", ""),
            "reasoning": analysis.get("reasoning", ""),
            "key_levels": analysis.get("key_levels", {}),
        }
        self.recent.append(entry)
        self._persist_recent()

    def get_recent(self, symbol: str = None, n: int = 5) -> list[dict]:
        entries = list(self.recent)
        if symbol:
            entries = [e for e in entries if e["symbol"] == symbol]
        return entries[-n:]

    def get_recent_summary(self, symbol: str, n: int = 3) -> str:
        entries = self.get_recent(symbol, n)
        if not entries:
            return "No prior analyses."
        lines = []
        for e in entries:
            ts = time.strftime("%H:%M", time.gmtime(e["timestamp"]))
            lines.append(
                f"- {ts} {e['timeframe']}: {e['action']} "
                f"(strength: {e['signal_strength']}, trend: {e['trend']}) "
                f"— {e['reasoning'][:120]}"
            )
        return "\n".join(lines)

    def get_bias(self, symbol: str) -> str:
        """Summarize recent trend bias across timeframes."""
        entries = self.get_recent(symbol, n=10)
        if not entries:
            return "No data."
        bullish = sum(1 for e in entries if e["trend"] == "bullish")
        bearish = sum(1 for e in entries if e["trend"] == "bearish")
        total = len(entries)
        return (
            f"Last {total} analyses: {bullish} bullish, {bearish} bearish, "
            f"{total - bullish - bearish} neutral"
        )

    def add_reflection(self, symbol: str, reflection: str):
        """Store a long-term learning from past outcomes."""
        self.reflections.append({
            "timestamp": time.time(),
            "symbol": symbol,
            "reflection": reflection,
        })
        # Keep last 50
        self.reflections = self.reflections[-50:]
        self._persist_reflections()

    def get_reflections(self, symbol: str = None, n: int = 5) -> str:
        entries = self.reflections
        if symbol:
            entries = [r for r in entries if r["symbol"] == symbol]
        entries = entries[-n:]
        if not entries:
            return "No reflections yet."
        return "\n".join(f"- {r['reflection']}" for r in entries)

    def _persist_recent(self):
        if not self._persist_dir:
            return
        path = self._persist_dir / "recent.jsonl"
        with open(path, "w") as f:
            for entry in self.recent:
                f.write(json.dumps(entry) + "\n")

    def _persist_reflections(self):
        if not self._persist_dir:
            return
        path = self._persist_dir / "reflections.json"
        with open(path, "w") as f:
            json.dump(self.reflections, f)

    def _load(self):
        if not self._persist_dir:
            return
        recent_path = self._persist_dir / "recent.jsonl"
        if recent_path.exists():
            with open(recent_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.recent.append(json.loads(line))

        reflect_path = self._persist_dir / "reflections.json"
        if reflect_path.exists():
            with open(reflect_path) as f:
                self.reflections = json.load(f)
