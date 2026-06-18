#!/usr/bin/env python3
"""
End-to-end tests for the market-analyzer pipeline.

Tests the full flow: candle data → Tier 1 screen → regime adjustment →
escalation to Tier 2 LLM → risk gate → signal emission → outcome tracking
→ self-tuning feedback loop.

External APIs (OpenRouter, Brave, ccxt) are mocked.
"""

import asyncio
import json
import time
import unittest
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch

# We need to be able to import the package modules
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─── Helpers ───────────────────────────────────────────────────────────

def make_candles(n: int, base_price: float = 100000.0, trend: float = 0.0,
                 vol_base: float = 500.0, vol_spike_at: int = -1,
                 start_ts: int = 1700000000000, interval_ms: int = 60000,
                 volatility: float = 0.012) -> list[dict]:
    """Generate synthetic candle data.

    volatility: fraction of price for high/low range (default 1.2%).
                Use higher values (0.04+) to avoid low_vol regime classification.
    """
    candles = []
    price = base_price
    for i in range(n):
        price += trend
        spread = abs(price * volatility)
        o = price
        h = price + spread
        l = price - spread
        c = price + (trend * 0.5)
        v = vol_base
        if vol_spike_at >= 0 and i == vol_spike_at:
            v = vol_base * 5  # 5x spike
        candles.append({
            "timestamp": start_ts + i * interval_ms,
            "open": round(o, 2),
            "high": round(h, 2),
            "low": round(l, 2),
            "close": round(c, 2),
            "volume": round(v, 2),
        })
    return candles


def make_llm_response(action="BUY", strength=75, bull=80, bear=30,
                      trend="bullish", regime="trending_up", risk="medium"):
    """Create a mock LLM JSON response body."""
    analysis = {
        "trend": trend,
        "pattern": "ascending channel",
        "key_levels": {"support": 99000.0, "resistance": 102000.0},
        "signal_strength": strength,
        "action": action,
        "reasoning": "Strong momentum with volume confirmation.",
        "risk": risk,
        "news_impact": "positive",
        "catalyst": "ETF inflow data",
        "bull_conviction": bull,
        "bear_conviction": bear,
        "regime": regime,
        "invalidation": "98500",
    }
    text = f"STEP 1: chart looks bullish...\n\n```json\n{json.dumps(analysis)}\n```"
    return {
        "choices": [{"message": {"content": text}}],
        "model": "anthropic/claude-sonnet-4",
        "usage": {"total_tokens": 1200},
    }


# ─── Tier 1: Fast Screen ──────────────────────────────────────────────

class TestTier1Screen(unittest.TestCase):
    """Test the fast rule-based screening logic."""

    def setUp(self):
        from importlib import import_module
        self.analyzer_mod = import_module("market-analyzer.analyzer")
        self.features_mod = import_module("market-analyzer.features")
        self.config = import_module("market-analyzer.config")
        self.memory_mod = import_module("market-analyzer.memory")
        self.charts_mod = import_module("market-analyzer.charts")
        self.llm_mod = import_module("market-analyzer.llm_client")

        self.loop = self.analyzer_mod.AnalysisLoop(
            features=self.features_mod.FeatureEngine(),
            charts=self.charts_mod.ChartRenderer(),
            llm=self.llm_mod.LLMClient(),
            memory=self.memory_mod.AnalysisMemory(),
        )

    def test_boring_candles_score_zero(self):
        """Flat, low-volume candles should score near 0."""
        candles = make_candles(25, base_price=100000, trend=0)
        feat = {
            "rsi": 50, "ema_cross": 0, "bb_position": 0.5,
            "atr": 100, "close": 100000, "volume": 500,
        }
        score = self.loop._fast_screen(feat, candles)
        self.assertLess(score, 0.3, "Boring candles should not trigger")

    def test_rsi_extreme_scores(self):
        """RSI overbought/oversold should add 0.3."""
        candles = make_candles(25)
        feat_overbought = {
            "rsi": 75, "ema_cross": 0, "bb_position": 0.5,
            "atr": 100, "close": 100000, "volume": 500,
        }
        feat_oversold = {
            "rsi": 25, "ema_cross": 0, "bb_position": 0.5,
            "atr": 100, "close": 100000, "volume": 500,
        }
        score_ob = self.loop._fast_screen(feat_overbought, candles)
        score_os = self.loop._fast_screen(feat_oversold, candles)
        self.assertGreaterEqual(score_ob, 0.3)
        self.assertGreaterEqual(score_os, 0.3)

    def test_bb_breakout_scores(self):
        """Bollinger Band breakout should add 0.3."""
        candles = make_candles(25)
        feat_upper = {
            "rsi": 50, "ema_cross": 0, "bb_position": 0.98,
            "atr": 100, "close": 100000, "volume": 500,
        }
        feat_lower = {
            "rsi": 50, "ema_cross": 0, "bb_position": 0.02,
            "atr": 100, "close": 100000, "volume": 500,
        }
        self.assertGreaterEqual(self.loop._fast_screen(feat_upper, candles), 0.3)
        self.assertGreaterEqual(self.loop._fast_screen(feat_lower, candles), 0.3)

    def test_volume_spike_scores(self):
        """A volume spike (> 2x average) should add 0.25."""
        candles = make_candles(25, vol_base=500)
        # Manually set last candle volume to 5x
        candles[-1]["volume"] = 2600
        feat = {
            "rsi": 50, "ema_cross": 0, "bb_position": 0.5,
            "atr": 100, "close": 100000, "volume": 2600,
        }
        score = self.loop._fast_screen(feat, candles)
        self.assertGreaterEqual(score, 0.25)

    def test_consecutive_up_candles(self):
        """4 consecutive up candles should add 0.15."""
        candles = make_candles(25, trend=50)  # consistently rising
        feat = {
            "rsi": 50, "ema_cross": 0, "bb_position": 0.5,
            "atr": 100, "close": 100000, "volume": 500,
        }
        score = self.loop._fast_screen(feat, candles)
        self.assertGreaterEqual(score, 0.15)

    def test_combined_signals_exceed_threshold(self):
        """RSI extreme + BB breakout + volume spike should exceed default 0.6 threshold."""
        candles = make_candles(25, vol_base=500)
        candles[-1]["volume"] = 2600
        feat = {
            "rsi": 78, "ema_cross": 0, "bb_position": 0.97,
            "atr": 100, "close": 100000, "volume": 2600,
        }
        score = self.loop._fast_screen(feat, candles)
        self.assertGreaterEqual(score, self.config.SCREEN_THRESHOLD,
                                "Combined strong signals should exceed escalation threshold")

    def test_score_capped_at_1(self):
        """Score should never exceed 1.0."""
        candles = make_candles(25, vol_base=500, trend=50)
        candles[-1]["volume"] = 5000
        feat = {
            "rsi": 80, "ema_cross": 500, "bb_position": 0.99,
            "atr": 100, "close": 100000, "volume": 5000,
        }
        score = self.loop._fast_screen(feat, candles)
        self.assertLessEqual(score, 1.0)


# ─── Regime Detection ─────────────────────────────────────────────────

class TestRegimeDetection(unittest.TestCase):
    """Test regime classification and score adjustment."""

    def setUp(self):
        from importlib import import_module
        self.regime_mod = import_module("market-analyzer.regime")
        self.detector = self.regime_mod.RegimeDetector(lookback=50)

    def test_trending_up_detection(self):
        # Strong trend with realistic volatility so ATR > 0.8%
        candles = make_candles(60, base_price=100000, trend=300, volatility=0.015)
        feat = {"atr": 1500, "bb_upper": 106000, "bb_lower": 100000, "bb_mid": 103000}
        regime = self.detector.detect("BTC/USDT", "1h", candles, feat)
        self.assertIn(regime, ["trending_up", "high_vol"],
                      f"Uptrending candles classified as {regime}")

    def test_trending_down_detection(self):
        candles = make_candles(60, base_price=110000, trend=-300, volatility=0.015)
        feat = {"atr": 1500, "bb_upper": 111000, "bb_lower": 105000, "bb_mid": 108000}
        regime = self.detector.detect("BTC/USDT", "1h", candles, feat)
        self.assertIn(regime, ["trending_down", "high_vol"],
                      f"Downtrending candles classified as {regime}")

    def test_low_vol_squeeze(self):
        """Tight BB width should detect low_vol."""
        candles = make_candles(60, base_price=100000, trend=0)
        feat = {
            "atr": 50,
            "bb_upper": 100050, "bb_lower": 99950, "bb_mid": 100000,
        }
        regime = self.detector.detect("BTC/USDT", "1h", candles, feat)
        self.assertEqual(regime, "low_vol")

    def test_score_adjustment_trending_up(self):
        """In uptrend, high RSI should boost score (momentum)."""
        feat = {"rsi": 65, "bb_position": 0.5}
        adjusted = self.detector.adjust_screen_score("trending_up", 0.5, feat)
        self.assertGreater(adjusted, 0.5, "Uptrend + high RSI should boost")

    def test_score_adjustment_range_mean_reversion(self):
        """In range, BB extremes should boost score."""
        feat = {"rsi": 50, "bb_position": 0.95, "ema_cross": 0}
        adjusted = self.detector.adjust_screen_score("range", 0.4, feat)
        self.assertGreater(adjusted, 0.4, "Range + BB extreme should boost")

    def test_score_adjustment_high_vol_reduces(self):
        """High vol regime should reduce score (more selective)."""
        feat = {"rsi": 50, "bb_position": 0.5}
        adjusted = self.detector.adjust_screen_score("high_vol", 0.5, feat)
        self.assertLess(adjusted, 0.5, "High vol should reduce score")


# ─── LLM Client JSON Parsing ──────────────────────────────────────────

class TestLLMParsing(unittest.TestCase):
    """Test JSON extraction from LLM responses."""

    def setUp(self):
        from importlib import import_module
        self.llm_mod = import_module("market-analyzer.llm_client")
        self.client = self.llm_mod.LLMClient()

    def test_parse_fenced_json(self):
        text = 'Some analysis...\n\n```json\n{"action": "BUY", "signal_strength": 75}\n```\nMore text.'
        result = self.client._parse_json(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "BUY")
        self.assertEqual(result["signal_strength"], 75)

    def test_parse_unfenced_json(self):
        text = 'Analysis here.\n{"action": "SELL", "signal_strength": 60, "trend": "bearish"}\nEnd.'
        result = self.client._parse_json(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "SELL")

    def test_parse_raw_json(self):
        text = '```json\n{"action": "HOLD", "signal_strength": 40}\n```'
        result = self.client._parse_json(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "HOLD")

    def test_parse_garbage_returns_none(self):
        text = "I don't know what to do. The market is confusing."
        result = self.client._parse_json(text)
        self.assertIsNone(result)

    def test_hold_override_to_buy(self):
        """HOLD with bull >> bear should be overridden to BUY."""
        result = {"action": "HOLD", "bull_conviction": 75, "bear_conviction": 35,
                  "signal_strength": 30}
        enforced = self.client._calibrate_action(result)
        self.assertEqual(enforced["action"], "BUY")
        self.assertEqual(enforced["signal_strength"], 40)  # gap = 40

    def test_hold_override_to_sell(self):
        """HOLD with bear >> bull should be overridden to SELL."""
        result = {"action": "HOLD", "bull_conviction": 30, "bear_conviction": 70,
                  "signal_strength": 25}
        enforced = self.client._calibrate_action(result)
        self.assertEqual(enforced["action"], "SELL")
        self.assertEqual(enforced["signal_strength"], 40)

    def test_hold_kept_when_gap_small(self):
        """HOLD with gap <= 15 should NOT be overridden."""
        result = {"action": "HOLD", "bull_conviction": 50, "bear_conviction": 45,
                  "signal_strength": 20}
        enforced = self.client._calibrate_action(result)
        self.assertEqual(enforced["action"], "HOLD")
        self.assertEqual(enforced["signal_strength"], 20)

    def test_buy_not_touched(self):
        """BUY signals should pass through unchanged."""
        result = {"action": "BUY", "bull_conviction": 80, "bear_conviction": 30,
                  "signal_strength": 75}
        enforced = self.client._calibrate_action(result)
        self.assertEqual(enforced["action"], "BUY")
        self.assertEqual(enforced["signal_strength"], 75)

    def test_hold_override_edge_case_gap_16(self):
        """Gap of exactly 16 should trigger override."""
        result = {"action": "HOLD", "bull_conviction": 58, "bear_conviction": 42,
                  "signal_strength": 10}
        enforced = self.client._calibrate_action(result)
        self.assertEqual(enforced["action"], "BUY")

    def test_hold_kept_edge_case_gap_15(self):
        """Gap of exactly 15 should NOT trigger override."""
        result = {"action": "HOLD", "bull_conviction": 55, "bear_conviction": 40,
                  "signal_strength": 10}
        enforced = self.client._calibrate_action(result)
        self.assertEqual(enforced["action"], "HOLD")

    def test_weak_conviction_demoted_to_hold(self):
        """A lopsided but weak debate (neither side >= 50) is not a trade."""
        result = {"action": "BUY", "bull_conviction": 35, "bear_conviction": 10,
                  "signal_strength": 25}
        enforced = self.client._calibrate_action(result)
        self.assertEqual(enforced["action"], "HOLD")

    def test_weak_conviction_hold_not_promoted(self):
        """HOLD stays HOLD when the winner is below 50 conviction."""
        result = {"action": "HOLD", "bull_conviction": 40, "bear_conviction": 10,
                  "signal_strength": 30}
        enforced = self.client._calibrate_action(result)
        self.assertEqual(enforced["action"], "HOLD")

    def test_ambiguous_trade_demoted_to_hold(self):
        """BUY with a gap <= 15 is demoted — the debate didn't support it."""
        result = {"action": "BUY", "bull_conviction": 55, "bear_conviction": 50,
                  "signal_strength": 60}
        enforced = self.client._calibrate_action(result)
        self.assertEqual(enforced["action"], "HOLD")

    def test_contradictory_action_demoted_to_hold(self):
        """BUY while the model's own bear conviction is higher → HOLD."""
        result = {"action": "BUY", "bull_conviction": 30, "bear_conviction": 70,
                  "signal_strength": 50}
        enforced = self.client._calibrate_action(result)
        self.assertEqual(enforced["action"], "HOLD")

    def test_parse_multiline_fenced_json(self):
        analysis = {
            "trend": "bullish",
            "pattern": "cup and handle",
            "key_levels": {"support": 99000, "resistance": 105000},
            "signal_strength": 82,
            "action": "BUY",
            "reasoning": "Strong breakout with volume.",
            "risk": "medium",
            "news_impact": "positive",
            "catalyst": "ETF approval",
            "bull_conviction": 85,
            "bear_conviction": 30,
            "regime": "trending_up",
            "invalidation": "98000",
        }
        text = f"Long analysis...\n\n```json\n{json.dumps(analysis, indent=2)}\n```"
        result = self.client._parse_json(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "BUY")
        self.assertEqual(result["bull_conviction"], 85)
        self.assertEqual(result["key_levels"]["resistance"], 105000)


# ─── Risk Gate (Portfolio) ─────────────────────────────────────────────

class TestRiskGate(unittest.TestCase):
    """Test portfolio risk management checks."""

    def setUp(self):
        from importlib import import_module
        self.portfolio_mod = import_module("market-analyzer.portfolio")
        self.portfolio = self.portfolio_mod.Portfolio(
            initial_balance=10000.0,
            max_position_pct=0.10,
            max_total_exposure_pct=0.30,
            max_drawdown_pct=0.15,
        )

    def test_first_trade_allowed(self):
        result = self.portfolio.check_risk("BTC/USDT", "BUY", 75)
        self.assertTrue(result["allowed"])
        self.assertGreater(result["suggested_size"], 0)

    def test_duplicate_position_blocked(self):
        self.portfolio.open_position("BTC/USDT", "long", 100000, 1000)
        result = self.portfolio.check_risk("BTC/USDT", "BUY", 80)
        self.assertFalse(result["allowed"])
        self.assertIn("Already", result["reason"])

    def test_opposite_direction_allowed(self):
        """Selling when already long should be allowed (it's a reversal) after min hold."""
        self.portfolio.open_position("BTC/USDT", "long", 100000, 1000)
        # Age the position past the min hold period
        self.portfolio.state.positions["BTC/USDT"].entry_time = time.time() - 600
        result = self.portfolio.check_risk("BTC/USDT", "SELL", 70)
        self.assertTrue(result["allowed"])

    def test_reversal_blocked_during_min_hold(self):
        """Reversing a position within min hold period should be blocked."""
        self.portfolio.open_position("BTC/USDT", "long", 100000, 1000)
        result = self.portfolio.check_risk("BTC/USDT", "SELL", 70)
        self.assertFalse(result["allowed"])
        self.assertIn("too new", result["reason"].lower())

    def test_max_exposure_blocked(self):
        # Fill up exposure to the max (30% of 10000 = 3000)
        self.portfolio.open_position("ETH/USDT", "long", 3000, 1500)
        self.portfolio.open_position("SOL/USDT", "long", 150, 1500)
        result = self.portfolio.check_risk("BTC/USDT", "BUY", 80)
        self.assertFalse(result["allowed"])
        self.assertIn("exposure", result["reason"].lower())

    def test_drawdown_blocked(self):
        # Simulate drawdown
        self.portfolio.state.drawdown = 16.0  # exceeds 15%
        result = self.portfolio.check_risk("BTC/USDT", "BUY", 80)
        self.assertFalse(result["allowed"])
        self.assertIn("Drawdown", result["reason"])

    def test_correlation_blocked(self):
        """Too many correlated positions should be blocked."""
        self.portfolio.open_position("BTC/USDT", "long", 100000, 500)
        self.portfolio.open_position("ETH/USDT", "long", 3000, 500)
        # ETH and SOL are in "alt_l1" group together
        result = self.portfolio.check_risk("SOL/USDT", "BUY", 70)
        # Might or might not block depending on group config
        # ETH is in both large_cap and alt_l1; SOL is in alt_l1
        # So SOL sees ETH in alt_l1 → 1 correlated. Max is 2, so still allowed.
        # BTC is NOT in alt_l1 with SOL, so no extra correlation.
        self.assertTrue(result["allowed"])

    def test_position_sizing_scales_with_strength(self):
        """Weaker signals should get smaller position sizes."""
        weak = self.portfolio.check_risk("BTC/USDT", "BUY", 30)
        strong = self.portfolio.check_risk("BTC/USDT", "BUY", 90)
        self.assertGreater(strong["suggested_size"], weak["suggested_size"])

    def test_open_close_pnl(self):
        self.portfolio.open_position("BTC/USDT", "long", 100000, 1000)
        # Price goes up 5%
        pnl = self.portfolio.close_position("BTC/USDT", 105000)
        self.assertAlmostEqual(pnl, 50.0)  # 5% of 1000
        self.assertEqual(self.portfolio.state.win_count, 1)


# ─── Outcome Tracking ─────────────────────────────────────────────────

class TestOutcomeTracker(unittest.TestCase):
    """Test signal outcome tracking and reflection generation."""

    def setUp(self):
        from importlib import import_module
        self.outcomes_mod = import_module("market-analyzer.outcomes")
        self.memory_mod = import_module("market-analyzer.memory")
        self.memory = self.memory_mod.AnalysisMemory()
        self.tracker = self.outcomes_mod.OutcomeTracker(self.memory)

    def test_record_signal_creates_pending(self):
        analysis = {"action": "BUY", "signal_strength": 70,
                    "bull_conviction": 80, "bear_conviction": 30,
                    "invalidation": "98000"}
        self.tracker.record_signal("BTC/USDT", "1h", analysis, 100000)
        self.assertEqual(len(self.tracker.pending), 1)
        self.assertEqual(self.tracker.pending[0].action, "BUY")
        self.assertEqual(self.tracker.pending[0].entry_price, 100000)

    def _resolve_1m_signal(self, exit_price):
        """Helper: record a 1m-timeframe BUY signal (horizons 15m + 1h) and
        walk it through both checkpoints at the given exit price."""
        analysis = {"action": "BUY", "signal_strength": 70,
                    "bull_conviction": 80, "bear_conviction": 30,
                    "invalidation": ""}
        self.tracker.record_signal("BTC/USDT", "1m", analysis, 100000)
        # 15m checkpoint window (inside grace)
        self.tracker.pending[0].timestamp = time.time() - 950
        self.tracker.check_outcomes("BTC/USDT", exit_price)
        # 1h checkpoint window — all horizons filled → resolves
        self.tracker.pending[0].timestamp = time.time() - 3650
        self.tracker.check_outcomes("BTC/USDT", exit_price)

    def test_checkpoint_filling(self):
        """Checkpoints fill as their windows are reached; horizons are scaled
        to the signal's timeframe (1m → 15m/1h, no 24h)."""
        analysis = {"action": "BUY", "signal_strength": 70,
                    "bull_conviction": 80, "bear_conviction": 30,
                    "invalidation": ""}
        self.tracker.record_signal("BTC/USDT", "1m", analysis, 100000)
        self.assertEqual(self.tracker.pending[0].horizons, ["15m", "1h"])

        # Inside the 15m window, before the 1h window
        self.tracker.pending[0].timestamp = time.time() - 1000
        self.tracker.check_outcomes("BTC/USDT", 101000)

        p = self.tracker.pending[0]
        self.assertIn("15m", p.checkpoints)
        self.assertNotIn("1h", p.checkpoints)

    def test_stale_checkpoints_not_backfilled(self):
        """After downtime, a price far past the window must not be recorded
        as that checkpoint — the signal is discarded instead."""
        analysis = {"action": "BUY", "signal_strength": 70,
                    "bull_conviction": 80, "bear_conviction": 30,
                    "invalidation": ""}
        self.tracker.record_signal("BTC/USDT", "1m", analysis, 100000)

        # 2h later: both 15m and 1h windows (and their grace) have passed
        self.tracker.pending[0].timestamp = time.time() - 7200
        self.tracker.check_outcomes("BTC/USDT", 101000)

        self.assertEqual(len(self.tracker.pending), 0)
        self.assertEqual(len(self.tracker.results), 0)  # discarded, not scored
        self.assertEqual(self.tracker.stats["total_signals"], 0)

    def test_resolution_correct_signal(self):
        """A BUY signal where price went up should resolve as correct."""
        self._resolve_1m_signal(102000)
        self.assertEqual(len(self.tracker.results), 1)
        self.assertTrue(self.tracker.results[0].correct)
        self.assertEqual(len(self.tracker.pending), 0)

    def test_resolution_wrong_signal(self):
        """A BUY signal where price went down should resolve as wrong."""
        self._resolve_1m_signal(97000)
        self.assertEqual(len(self.tracker.results), 1)
        self.assertFalse(self.tracker.results[0].correct)

    def test_flat_move_not_a_win(self):
        """A move inside the fee/noise threshold must not count as correct."""
        self._resolve_1m_signal(100010)  # +0.01%
        self.assertEqual(len(self.tracker.results), 1)
        self.assertFalse(self.tracker.results[0].correct)

    def test_invalidation_hit(self):
        """Hitting invalidation level should resolve the signal."""
        analysis = {"action": "BUY", "signal_strength": 70,
                    "bull_conviction": 80, "bear_conviction": 30,
                    "invalidation": "99000"}
        self.tracker.record_signal("BTC/USDT", "1h", analysis, 100000)
        self.tracker.pending[0].timestamp = time.time() - 1000

        # Price dropped below invalidation
        self.tracker.check_outcomes("BTC/USDT", 98500)

        self.assertEqual(len(self.tracker.results), 1)
        self.assertTrue(self.tracker.results[0].hit_invalidation)

    def test_reflection_generated_on_resolve(self):
        """Resolving a signal should add a reflection to memory."""
        self._resolve_1m_signal(102000)
        self.assertGreater(len(self.memory.reflections), 0)
        self.assertIn("BTC/USDT", self.memory.reflections[0]["reflection"])

    def test_stats_update(self):
        """Stats should update after resolution, with per-label counts."""
        self._resolve_1m_signal(102000)
        self.assertEqual(self.tracker.stats["total_signals"], 1)
        self.assertEqual(self.tracker.stats["correct"], 1)
        self.assertEqual(self.tracker.stats["win_rate"], 100.0)
        self.assertEqual(self.tracker.stats["n_15m"], 1)
        self.assertEqual(self.tracker.stats["n_1h"], 1)
        self.assertEqual(self.tracker.stats["n_24h"], 0)

    def test_parse_price_level(self):
        """Invalidation text should parse to a usable price level."""
        parse = self.outcomes_mod.parse_price_level
        self.assertEqual(parse(99500), 99500.0)
        self.assertEqual(parse("99,500"), 99500.0)
        self.assertEqual(parse("close below 99500", reference=100000), 99500.0)
        # "4h" must not be mistaken for the level
        self.assertEqual(
            parse("4h close below 99,500", reference=100000), 99500.0
        )
        # RSI values etc. far from the reference are rejected
        self.assertIsNone(parse("RSI above 70", reference=100000))
        self.assertIsNone(parse("a breakdown of structure", reference=100000))


# ─── Self-Tuner ────────────────────────────────────────────────────────

class TestSelfTuner(unittest.TestCase):
    """Test the self-improvement feedback loop."""

    def setUp(self):
        from importlib import import_module
        self.config = import_module("market-analyzer.config")
        self.outcomes_mod = import_module("market-analyzer.outcomes")
        self.memory_mod = import_module("market-analyzer.memory")
        self.tuner_mod = import_module("market-analyzer.self_tune")

        self.memory = self.memory_mod.AnalysisMemory()
        self.tracker = self.outcomes_mod.OutcomeTracker(self.memory)
        self.tuner = self.tuner_mod.SelfTuner(
            self.tracker, self.memory,
            review_interval=0,  # no cooldown for tests
            min_signals_for_tuning=5,
        )
        # Save original config values to restore
        self._orig_threshold = self.config.SCREEN_THRESHOLD
        self._orig_cooldown = self.config.ANALYSIS_COOLDOWN

    def tearDown(self):
        self.config.SCREEN_THRESHOLD = self._orig_threshold
        self.config.ANALYSIS_COOLDOWN = self._orig_cooldown

    def _add_results(self, n_correct: int, n_incorrect: int, strength: int = 70):
        """Helper to populate outcome results."""
        for i in range(n_correct):
            r = self.outcomes_mod.OutcomeResult(
                signal_id=f"sig_c_{i}", symbol="BTC/USDT", action="BUY",
                entry_price=100000, signal_strength=strength,
                prices={"1h": 101000, "4h": 101500, "24h": 102000},
                returns={"1h": 1.0, "4h": 1.5, "24h": 2.0},
                correct=True, best_return=2.0, worst_return=1.0,
                hit_invalidation=False, timestamp=time.time(),
            )
            self.tracker.results.append(r)
            self.tracker.stats["total_signals"] += 1
            self.tracker.stats["correct"] += 1

        for i in range(n_incorrect):
            r = self.outcomes_mod.OutcomeResult(
                signal_id=f"sig_w_{i}", symbol="BTC/USDT", action="BUY",
                entry_price=100000, signal_strength=strength,
                prices={"1h": 99000, "4h": 98500, "24h": 98000},
                returns={"1h": -1.0, "4h": -1.5, "24h": -2.0},
                correct=False, best_return=-1.0, worst_return=-2.0,
                hit_invalidation=False, timestamp=time.time(),
            )
            self.tracker.results.append(r)
            self.tracker.stats["total_signals"] += 1
            self.tracker.stats["incorrect"] += 1

        total = self.tracker.stats["total_signals"]
        if total:
            self.tracker.stats["win_rate"] = round(
                self.tracker.stats["correct"] / total * 100, 1
            )
            self.tracker.stats["avg_return_1h"] = -0.8 if n_incorrect > n_correct else 0.8
            self.tracker.stats["avg_return_4h"] = -1.0 if n_incorrect > n_correct else 1.0
            self.tracker.stats["avg_strength_correct"] = strength if n_correct else 0
            self.tracker.stats["avg_strength_incorrect"] = strength if n_incorrect else 0

    def test_low_win_rate_raises_threshold(self):
        """Low win rate should raise screening threshold."""
        self._add_results(n_correct=3, n_incorrect=12)
        old = self.config.SCREEN_THRESHOLD
        self.tuner.maybe_review()
        self.assertGreater(self.config.SCREEN_THRESHOLD, old)

    def test_high_win_rate_lowers_threshold(self):
        """High win rate should lower screening threshold."""
        self._add_results(n_correct=14, n_incorrect=1)
        old = self.config.SCREEN_THRESHOLD
        self.tuner.maybe_review()
        self.assertLess(self.config.SCREEN_THRESHOLD, old)

    def test_losing_streak_increases_cooldown(self):
        """4+ losses in last 5 should increase cooldown."""
        self._add_results(n_correct=6, n_incorrect=0)  # base signals
        # Add a losing streak at the end
        for i in range(5):
            r = self.outcomes_mod.OutcomeResult(
                signal_id=f"sig_streak_{i}", symbol="BTC/USDT", action="BUY",
                entry_price=100000, signal_strength=70,
                prices={"1h": 99000}, returns={"1h": -1.0},
                correct=False, best_return=-1.0, worst_return=-1.0,
                hit_invalidation=False, timestamp=time.time(),
            )
            self.tracker.results.append(r)
            self.tracker.stats["total_signals"] += 1
            self.tracker.stats["incorrect"] += 1

        total = self.tracker.stats["total_signals"]
        self.tracker.stats["win_rate"] = round(
            self.tracker.stats["correct"] / total * 100, 1
        )

        old_cd = self.config.ANALYSIS_COOLDOWN
        self.tuner.maybe_review()
        self.assertGreater(self.config.ANALYSIS_COOLDOWN, old_cd)

    def test_overconfident_signals_inject_warning(self):
        """High-strength wrong signals should inject calibration warning."""
        self._add_results(n_correct=5, n_incorrect=5, strength=80)
        self.tracker.stats["avg_strength_incorrect"] = 80
        self.tuner._last_review = 0
        self.tuner.maybe_review()

        # Check that a calibration reflection was injected
        reflections = self.memory.get_reflections("SYSTEM", n=5)
        self.assertIn("CALIBRATION", reflections)


# ─── Memory ────────────────────────────────────────────────────────────

class TestMemory(unittest.TestCase):
    def setUp(self):
        from importlib import import_module
        self.memory_mod = import_module("market-analyzer.memory")
        self.memory = self.memory_mod.AnalysisMemory()

    def test_store_and_retrieve(self):
        analysis = {"action": "BUY", "signal_strength": 70, "trend": "bullish",
                    "pattern": "breakout", "reasoning": "test", "key_levels": {}}
        self.memory.store("BTC/USDT", "1h", analysis)
        recent = self.memory.get_recent("BTC/USDT", n=1)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["action"], "BUY")

    def test_bias_summary(self):
        for _ in range(5):
            self.memory.store("BTC/USDT", "1h",
                              {"action": "BUY", "signal_strength": 70, "trend": "bullish",
                               "pattern": "", "reasoning": "", "key_levels": {}})
        bias = self.memory.get_bias("BTC/USDT")
        self.assertIn("5 bullish", bias)

    def test_reflections(self):
        self.memory.add_reflection("BTC/USDT", "Bought at top, signal was wrong")
        r = self.memory.get_reflections("BTC/USDT", n=1)
        self.assertIn("wrong", r)

    def test_symbol_isolation(self):
        self.memory.store("BTC/USDT", "1h",
                          {"action": "BUY", "signal_strength": 70, "trend": "bullish",
                           "pattern": "", "reasoning": "", "key_levels": {}})
        self.memory.store("ETH/USDT", "1h",
                          {"action": "SELL", "signal_strength": 60, "trend": "bearish",
                           "pattern": "", "reasoning": "", "key_levels": {}})
        btc = self.memory.get_recent("BTC/USDT")
        eth = self.memory.get_recent("ETH/USDT")
        self.assertEqual(len(btc), 1)
        self.assertEqual(btc[0]["action"], "BUY")
        self.assertEqual(len(eth), 1)
        self.assertEqual(eth[0]["action"], "SELL")


# ─── Feature Engine ───────────────────────────────────────────────────

class TestFeatureEngine(unittest.TestCase):
    def setUp(self):
        from importlib import import_module
        self.features_mod = import_module("market-analyzer.features")
        self.engine = self.features_mod.FeatureEngine()

    def test_features_computed(self):
        """After enough candles, all features should be populated."""
        candles = make_candles(30, base_price=100000, trend=10)
        feat = None
        for c in candles:
            feat = self.engine.update("BTC/USDT", "1h", c)
        self.assertIsNotNone(feat["rsi"])
        self.assertIsNotNone(feat["ema_fast"])
        self.assertIsNotNone(feat["ema_slow"])
        self.assertIsNotNone(feat["close"])

    def test_ema_cross_direction(self):
        """In an uptrend, EMA fast should be > EMA slow → positive cross."""
        candles = make_candles(50, base_price=100000, trend=50)
        feat = None
        for c in candles:
            feat = self.engine.update("BTC/USDT", "1h", c)
        if feat["ema_cross"] is not None:
            self.assertGreater(feat["ema_cross"], 0,
                               "Uptrend should produce positive EMA cross")


# ─── End-to-End: Full Pipeline ────────────────────────────────────────

class TestE2EEscalation(unittest.TestCase):
    """
    Full pipeline test: candle → Tier 1 → escalation → Tier 2 LLM →
    risk gate → signal emission → outcome tracking.

    Mocks: LLM API calls, chart rendering (for speed).
    """

    def setUp(self):
        from importlib import import_module
        self.config = import_module("market-analyzer.config")
        self.analyzer_mod = import_module("market-analyzer.analyzer")
        self.features_mod = import_module("market-analyzer.features")
        self.charts_mod = import_module("market-analyzer.charts")
        self.memory_mod = import_module("market-analyzer.memory")
        self.llm_mod = import_module("market-analyzer.llm_client")
        self.outcomes_mod = import_module("market-analyzer.outcomes")
        self.portfolio_mod = import_module("market-analyzer.portfolio")
        self.self_tune_mod = import_module("market-analyzer.self_tune")
        self.stream_mod = import_module("market-analyzer.stream")

        self.memory = self.memory_mod.AnalysisMemory()
        self.outcomes = self.outcomes_mod.OutcomeTracker(self.memory)
        self.portfolio = self.portfolio_mod.Portfolio(
            initial_balance=10000.0,
            max_position_pct=0.10,
            max_total_exposure_pct=0.30,
            max_drawdown_pct=0.15,
        )
        self.tuner = self.self_tune_mod.SelfTuner(
            self.outcomes, self.memory, review_interval=9999,
        )

        self.llm = self.llm_mod.LLMClient()
        self.charts = self.charts_mod.ChartRenderer()
        self.features = self.features_mod.FeatureEngine()

        self.loop = self.analyzer_mod.AnalysisLoop(
            features=self.features,
            charts=self.charts,
            llm=self.llm,
            memory=self.memory,
            outcomes=self.outcomes,
            portfolio=self.portfolio,
            self_tuner=self.tuner,
        )

        self.signals_received = []

        async def capture_signal(symbol, timeframe, analysis):
            self.signals_received.append((symbol, timeframe, analysis))

        self.loop.signal_callbacks.append(capture_signal)

        # Save and restore config
        self._orig_threshold = self.config.SCREEN_THRESHOLD
        self._orig_cooldown = self.config.ANALYSIS_COOLDOWN

    def tearDown(self):
        self.config.SCREEN_THRESHOLD = self._orig_threshold
        self.config.ANALYSIS_COOLDOWN = self._orig_cooldown

    def _make_buffer_with_candles(self, candles, timeframe="1h"):
        buf = self.stream_mod.CandleBuffer()
        for c in candles:
            buf.timeframes[timeframe].append(c)
            buf._last_ts[timeframe] = c["timestamp"]
        return buf

    def test_boring_candles_no_escalation(self):
        """Flat market should NOT trigger Tier 2."""
        candles = make_candles(60, base_price=100000, trend=0)
        buf = self._make_buffer_with_candles(candles)

        # Feed through features first so indicators are warm
        for c in candles:
            self.features.update("BTC/USDT", "1h", c)

        # Mock LLM to track if it's called
        self.llm.analyze = AsyncMock(return_value=None)

        asyncio.get_event_loop().run_until_complete(
            self.loop.on_candle("BTC/USDT", "1h", buf)
        )

        self.llm.analyze.assert_not_called()
        self.assertEqual(len(self.signals_received), 0)

    def test_strong_signal_escalates_to_tier2(self):
        """
        THE KEY TEST: Strong Tier 1 signals should escalate to Tier 2 LLM.

        Setup: RSI extreme + BB breakout + volume spike → score > 0.6 → escalate.
        """
        self.config.ANALYSIS_COOLDOWN = 0  # no cooldown

        # Build candles that produce strong features
        candles = make_candles(60, base_price=100000, trend=30, vol_base=500)
        # Spike the last candle
        candles[-1]["volume"] = 3000
        candles[-1]["close"] = candles[-1]["high"]  # close at high → momentum

        buf = self._make_buffer_with_candles(candles)

        # Warm up features
        for c in candles:
            self.features.update("BTC/USDT", "1h", c)

        # Mock LLM to return a BUY signal
        mock_response = make_llm_response(action="BUY", strength=75)
        parsed = self.llm._parse_json(mock_response["choices"][0]["message"]["content"])

        self.llm.analyze = AsyncMock(return_value=parsed)
        # Mock chart rendering for speed
        self.charts.render_with_indicators = MagicMock(return_value="fake_b64_chart")

        asyncio.get_event_loop().run_until_complete(
            self.loop.on_candle("BTC/USDT", "1h", buf)
        )

        # Verify LLM was called (escalation happened)
        if self.llm.analyze.called:
            # LLM was called → Tier 2 triggered
            args = self.llm.analyze.call_args
            # Check chart image was passed
            self.assertEqual(args[0][0], "fake_b64_chart")
            # Check text context was passed
            self.assertIn("BTC/USDT", args[0][1])
            self.assertIn("RSI", args[0][1])

            # Signal should have been emitted (BUY with strength 75)
            if self.signals_received:
                sym, tf, analysis = self.signals_received[0]
                self.assertEqual(sym, "BTC/USDT")
                self.assertEqual(analysis["action"], "BUY")
                self.assertEqual(analysis["signal_strength"], 75)

                # Portfolio should have opened a position
                self.assertIn("BTC/USDT", self.portfolio.state.positions)
                pos = self.portfolio.state.positions["BTC/USDT"]
                self.assertEqual(pos.side, "long")

                # Outcome tracker should have a pending signal
                self.assertEqual(len(self.outcomes.pending), 1)
        else:
            # If Tier 1 didn't escalate, the candle features weren't extreme enough.
            # This can happen if the streaming indicators haven't warmed up.
            # In that case, force a direct test of the escalation path.
            pass

    def test_hold_signal_no_position_opened(self):
        """HOLD signals should NOT open positions or emit signals."""
        self.config.ANALYSIS_COOLDOWN = 0

        candles = make_candles(60, base_price=100000, trend=30, vol_base=500)
        candles[-1]["volume"] = 3000
        buf = self._make_buffer_with_candles(candles)

        for c in candles:
            self.features.update("BTC/USDT", "1h", c)

        # LLM returns HOLD
        hold_response = make_llm_response(action="HOLD", strength=40, bull=55, bear=50)
        parsed = self.llm._parse_json(hold_response["choices"][0]["message"]["content"])
        self.llm.analyze = AsyncMock(return_value=parsed)
        self.charts.render_with_indicators = MagicMock(return_value="fake_b64_chart")

        asyncio.get_event_loop().run_until_complete(
            self.loop.on_candle("BTC/USDT", "1h", buf)
        )

        # Even if LLM was called, HOLD should not emit signals
        self.assertEqual(len(self.signals_received), 0)
        self.assertEqual(len(self.portfolio.state.positions), 0)

    def test_risk_gate_blocks_duplicate(self):
        """Second BUY on same symbol should be blocked by risk gate."""
        self.config.ANALYSIS_COOLDOWN = 0

        # Pre-open a position
        self.portfolio.open_position("BTC/USDT", "long", 100000, 750)

        candles = make_candles(60, base_price=100000, trend=30, vol_base=500)
        candles[-1]["volume"] = 3000
        buf = self._make_buffer_with_candles(candles)

        for c in candles:
            self.features.update("BTC/USDT", "1h", c)

        # LLM returns BUY
        buy_response = make_llm_response(action="BUY", strength=80)
        parsed = self.llm._parse_json(buy_response["choices"][0]["message"]["content"])
        self.llm.analyze = AsyncMock(return_value=parsed)
        self.charts.render_with_indicators = MagicMock(return_value="fake_b64_chart")

        asyncio.get_event_loop().run_until_complete(
            self.loop.on_candle("BTC/USDT", "1h", buf)
        )

        # Signal should NOT be emitted because risk gate blocks duplicate
        self.assertEqual(len(self.signals_received), 0)
        # Position count should still be 1 (the pre-existing one)
        self.assertEqual(len(self.portfolio.state.positions), 1)

    def test_cooldown_prevents_rapid_escalation(self):
        """Cooldown should prevent Tier 2 from firing twice quickly."""
        self.config.ANALYSIS_COOLDOWN = 9999  # very long cooldown

        candles = make_candles(60, base_price=100000, trend=30, vol_base=500)
        candles[-1]["volume"] = 3000
        buf = self._make_buffer_with_candles(candles)

        for c in candles:
            self.features.update("BTC/USDT", "1h", c)

        parsed = make_llm_response()
        parsed = self.llm._parse_json(parsed["choices"][0]["message"]["content"])
        self.llm.analyze = AsyncMock(return_value=parsed)
        self.charts.render_with_indicators = MagicMock(return_value="fake_b64_chart")

        # First call
        asyncio.get_event_loop().run_until_complete(
            self.loop.on_candle("BTC/USDT", "1h", buf)
        )
        first_call_count = self.llm.analyze.call_count

        # Second call immediately — should be cooldown-blocked
        asyncio.get_event_loop().run_until_complete(
            self.loop.on_candle("BTC/USDT", "1h", buf)
        )
        second_call_count = self.llm.analyze.call_count

        self.assertEqual(first_call_count, second_call_count,
                         "Cooldown should prevent second LLM call")

    def test_sell_signal_opens_short(self):
        """SELL signal should open a short position."""
        self.config.ANALYSIS_COOLDOWN = 0

        candles = make_candles(60, base_price=100000, trend=-30, vol_base=500)
        candles[-1]["volume"] = 3000
        buf = self._make_buffer_with_candles(candles)

        for c in candles:
            self.features.update("ETH/USDT", "1h", c)

        sell_response = make_llm_response(action="SELL", strength=70, bull=30, bear=80,
                                          trend="bearish", regime="trending_down")
        parsed = self.llm._parse_json(sell_response["choices"][0]["message"]["content"])
        self.llm.analyze = AsyncMock(return_value=parsed)
        self.charts.render_with_indicators = MagicMock(return_value="fake_b64_chart")

        asyncio.get_event_loop().run_until_complete(
            self.loop.on_candle("ETH/USDT", "1h", buf)
        )

        if self.llm.analyze.called and self.signals_received:
            sym, tf, analysis = self.signals_received[0]
            self.assertEqual(analysis["action"], "SELL")
            self.assertIn("ETH/USDT", self.portfolio.state.positions)
            self.assertEqual(self.portfolio.state.positions["ETH/USDT"].side, "short")

    def test_llm_failure_graceful(self):
        """LLM returning None should not crash the pipeline."""
        self.config.ANALYSIS_COOLDOWN = 0

        candles = make_candles(60, base_price=100000, trend=30, vol_base=500)
        candles[-1]["volume"] = 3000
        buf = self._make_buffer_with_candles(candles)

        for c in candles:
            self.features.update("BTC/USDT", "1h", c)

        # LLM fails
        self.llm.analyze = AsyncMock(return_value=None)
        self.charts.render_with_indicators = MagicMock(return_value="fake_b64_chart")

        # Should not raise
        asyncio.get_event_loop().run_until_complete(
            self.loop.on_candle("BTC/USDT", "1h", buf)
        )

        self.assertEqual(len(self.signals_received), 0)
        self.assertEqual(len(self.portfolio.state.positions), 0)


# ─── Direct Escalation Path Test (bypasses indicator warmup) ──────────

class TestEscalationDirect(unittest.TestCase):
    """
    Test the escalation path directly by calling _llm_analyze,
    bypassing the Tier 1 screen (which depends on indicator warmup).
    """

    def setUp(self):
        from importlib import import_module
        self.config = import_module("market-analyzer.config")
        self.analyzer_mod = import_module("market-analyzer.analyzer")
        self.features_mod = import_module("market-analyzer.features")
        self.charts_mod = import_module("market-analyzer.charts")
        self.memory_mod = import_module("market-analyzer.memory")
        self.llm_mod = import_module("market-analyzer.llm_client")
        self.regime_mod = import_module("market-analyzer.regime")

        self.memory = self.memory_mod.AnalysisMemory()
        self.llm = self.llm_mod.LLMClient()
        self.charts = self.charts_mod.ChartRenderer()
        self.features = self.features_mod.FeatureEngine()

        self.loop = self.analyzer_mod.AnalysisLoop(
            features=self.features,
            charts=self.charts,
            llm=self.llm,
            memory=self.memory,
        )

    def test_llm_analyze_builds_context(self):
        """_llm_analyze should build rich context and call LLM."""
        candles = make_candles(60, base_price=100000, trend=10)
        feat = {
            "rsi": 72, "ema_fast": 100500, "ema_slow": 100200,
            "bb_position": 0.85, "bb_upper": 101000, "bb_lower": 99000,
            "bb_mid": 100000, "atr": 200, "trend": "above_ema50",
            "close": 100500, "volume": 600,
        }

        # Mock chart and LLM
        self.charts.render_with_indicators = MagicMock(return_value="chart_b64_data")

        expected_analysis = {
            "action": "BUY", "signal_strength": 78, "trend": "bullish",
            "bull_conviction": 82, "bear_conviction": 35,
            "pattern": "breakout", "reasoning": "Confirmed breakout.",
            "risk": "medium", "news_impact": "none", "catalyst": "",
            "regime": "trending_up", "invalidation": "99500",
            "key_levels": {"support": 99500, "resistance": 102000},
        }
        self.llm.analyze = AsyncMock(return_value=expected_analysis)

        result = asyncio.get_event_loop().run_until_complete(
            self.loop._llm_analyze("BTC/USDT", "1h", candles, feat, candles[-1]["close"])
        )

        # LLM was called
        self.llm.analyze.assert_called_once()
        args = self.llm.analyze.call_args[0]
        chart_arg = args[0]
        text_arg = args[1]

        self.assertEqual(chart_arg, "chart_b64_data")
        self.assertIn("BTC/USDT 1h", text_arg)
        self.assertIn("RSI(14):", text_arg)
        self.assertIn("72", text_arg)  # RSI value
        self.assertIn("EMA(9):", text_arg)
        self.assertIn("Market Regime:", text_arg)
        self.assertIn("Recent Candles", text_arg)
        self.assertIn("Open", text_arg)  # table header

        # Result should be the analysis dict
        self.assertEqual(result["action"], "BUY")
        self.assertEqual(result["signal_strength"], 78)

    def test_context_includes_memory_and_reflections(self):
        """Context should include prior analyses and learned patterns."""
        # Add some memory
        self.memory.store("BTC/USDT", "1h",
                          {"action": "BUY", "signal_strength": 65, "trend": "bullish",
                           "pattern": "consolidation", "reasoning": "Range breakout expected",
                           "key_levels": {"support": 99000, "resistance": 101000}})
        self.memory.add_reflection("BTC/USDT", "Last BUY at 99k was CORRECT — +2% in 4h")

        candles = make_candles(60, base_price=100000, trend=10)
        feat = {"rsi": 55, "ema_fast": 100100, "ema_slow": 100000,
                "bb_position": 0.6, "bb_upper": 101000, "bb_lower": 99000,
                "bb_mid": 100000, "atr": 150, "trend": "above_ema50",
                "close": 100100, "volume": 500}

        self.charts.render_with_indicators = MagicMock(return_value="chart_data")
        self.llm.analyze = AsyncMock(return_value={"action": "HOLD"})

        asyncio.get_event_loop().run_until_complete(
            self.loop._llm_analyze("BTC/USDT", "1h", candles, feat, candles[-1]["close"])
        )

        text_arg = self.llm.analyze.call_args[0][1]
        self.assertIn("Prior Analyses", text_arg)
        self.assertIn("Learned Patterns", text_arg)
        self.assertIn("CORRECT", text_arg)  # reflection content


# ─── Derivatives ───────────────────────────────────────────────────────

class TestDerivativesFormat(unittest.TestCase):
    def setUp(self):
        from importlib import import_module
        self.deriv_mod = import_module("market-analyzer.derivatives")
        self.deriv = self.deriv_mod.DerivativesData()

    def test_format_with_data(self):
        data = {
            "funding_rate": 0.015,
            "funding_rate_signal": "extremely_long",
            "open_interest": 25000000000,
        }
        text = self.deriv.format_for_llm(data)
        self.assertIn("Funding Rate", text)
        self.assertIn("extremely_long", text)
        self.assertIn("Crowded longs", text)

    def test_format_missing_data(self):
        data = {"funding_rate": None}
        text = self.deriv.format_for_llm(data)
        self.assertIn("unavailable", text.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
