#!/usr/bin/env python3
"""
Test that the structured debate is actually happening.

The system prompt requires 7 steps before the JSON output:
  1. CHART READ
  2. INDICATOR ASSESSMENT
  3. NEWS & RESEARCH DIGEST
  4. BULL CASE
  5. BEAR CASE
  6. REGIME CHECK
  7. SYNTHESIS & DECISION

This test captures the raw LLM text (before JSON extraction) and verifies
the debate structure exists, not just the final JSON.
"""

import asyncio
import json
import os
import re
import sys
import time
import random
import unittest

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_realistic_candles(n, base_price, trend, volatility=0.008, seed=42):
    rng = random.Random(seed)
    candles = []
    price = base_price
    for i in range(n):
        drift = trend + rng.gauss(0, abs(trend) * 0.5 + volatility * price * 0.1)
        price += drift
        body = abs(rng.gauss(0, price * volatility * 0.5))
        wick_up = abs(rng.gauss(0, price * volatility * 0.3))
        wick_down = abs(rng.gauss(0, price * volatility * 0.3))
        if drift >= 0:
            o, c = price - body, price
        else:
            o, c = price, price - body
        h = max(o, c) + wick_up
        l = min(o, c) - wick_down
        v = max(50, rng.gauss(800, 300))
        candles.append({
            "timestamp": 1700000000000 + i * 3600000,
            "open": round(o, 2), "high": round(h, 2),
            "low": round(l, 2), "close": round(c, 2),
            "volume": round(v, 2),
        })
    return candles


def _skip_if_no_key():
    from importlib import import_module
    cfg = import_module("market-analyzer.config")
    if not cfg.OPENROUTER_API_KEY:
        raise unittest.SkipTest("OPENROUTER_API_KEY not set")


class TestDebateStructure(unittest.TestCase):
    """Verify the LLM actually performs the structured bull/bear debate."""

    @classmethod
    def setUpClass(cls):
        _skip_if_no_key()
        from importlib import import_module
        cls.config = import_module("market-analyzer.config")
        cls.llm_mod = import_module("market-analyzer.llm_client")
        cls.charts_mod = import_module("market-analyzer.charts")
        cls.features_mod = import_module("market-analyzer.features")

    def _get_raw_llm_response(self, candles, symbol, timeframe):
        """Call OpenRouter directly and return the RAW text + parsed JSON."""
        engine = self.features_mod.FeatureEngine()
        renderer = self.charts_mod.ChartRenderer()

        feat = None
        feat_list = []
        for c in candles:
            feat = engine.update(symbol, timeframe, c)
            feat_list.append(feat)

        chart_b64 = renderer.render_with_indicators(
            candles[-60:], feat_list[-60:], title=f"{symbol} {timeframe}",
        )

        rsi_str = f"{feat['rsi']:.1f}" if feat.get("rsi") else "N/A"
        bb_pos_str = f"{feat['bb_position']:.2f}" if feat.get("bb_position") else "N/A"
        ema_fast_str = f"{feat['ema_fast']:.2f}" if feat.get("ema_fast") else "N/A"
        ema_slow_str = f"{feat['ema_slow']:.2f}" if feat.get("ema_slow") else "N/A"
        atr_str = f"{feat['atr']:.2f}" if feat.get("atr") else "N/A"

        context_candles = candles[-20:]
        candle_text = "| Time | Open | High | Low | Close | Volume |\n"
        candle_text += "|------|------|------|-----|-------|--------|\n"
        for c in context_candles:
            ts = time.strftime("%m-%d %H:%M", time.gmtime(c["timestamp"] / 1000))
            candle_text += (
                f"| {ts} | {c['open']:.2f} | {c['high']:.2f} | "
                f"{c['low']:.2f} | {c['close']:.2f} | {c['volume']:.0f} |\n"
            )

        text_context = f"""## {symbol} {timeframe} — Live Analysis

**Current Price:** {feat['close']:.2f}
**RSI(14):** {rsi_str}
**EMA(9):** {ema_fast_str}
**EMA(21):** {ema_slow_str}
**BB Position:** {bb_pos_str} (0=lower band, 1=upper band)
**ATR(14):** {atr_str}
**Trend:** {feat.get('trend', 'N/A')}

### Recent Candles
{candle_text}

### Prior Analyses
No prior analyses.

### News (RSS/CryptoPanic)
No news feed data.

### Derivatives (Funding Rate / Open Interest)
No derivatives data.

### Signal Track Record
No signals tracked yet.

### Portfolio State
**Balance:** $10,000.00 | **Equity:** $10,000.00
**No open positions.**
"""

        content = []
        if chart_b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{chart_b64}"},
            })
        content.append({"type": "text", "text": text_context})

        payload = {
            "model": self.config.LLM_MODEL,
            "max_tokens": self.config.LLM_MAX_TOKENS,
            "messages": [
                {"role": "system", "content": self.llm_mod.SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
        }

        async def call():
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self.config.OPENROUTER_BASE_URL}/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.config.OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://starchild.ai",
                        "X-Title": "Market Analyzer Test",
                    },
                )
                resp.raise_for_status()
                return resp.json()

        data = asyncio.get_event_loop().run_until_complete(call())
        raw_text = data["choices"][0]["message"]["content"]
        tokens = data.get("usage", {}).get("total_tokens", 0)

        # Parse JSON from the raw text
        llm_client = self.llm_mod.LLMClient()
        parsed = llm_client._parse_json(raw_text)

        return raw_text, parsed, tokens

    def test_debate_steps_present(self):
        """Verify all 7 debate steps appear in the raw LLM output."""
        candles = make_realistic_candles(60, base_price=100000, trend=50, seed=100)

        print("\n[DEBATE TEST] Calling LLM and inspecting raw reasoning text...")
        raw_text, parsed, tokens = self._get_raw_llm_response(
            candles, "BTC/USDT", "1h"
        )
        print(f"[DEBATE TEST] {tokens} tokens, {len(raw_text)} chars")

        # Check each debate step exists in the raw text
        text_lower = raw_text.lower()

        steps = {
            "CHART READ": [
                r"step\s*1|chart\s*read",
            ],
            "INDICATOR ASSESSMENT": [
                r"step\s*2|indicator\s*assess",
            ],
            "NEWS & RESEARCH": [
                r"step\s*3|news.*research|news.*digest",
            ],
            "BULL CASE": [
                r"step\s*4|bull\s*case",
            ],
            "BEAR CASE": [
                r"step\s*5|bear\s*case",
            ],
            "REGIME CHECK": [
                r"step\s*6|regime\s*check",
            ],
            "SYNTHESIS": [
                r"step\s*7|synthe",
            ],
        }

        found = {}
        missing = []
        for step_name, patterns in steps.items():
            step_found = any(re.search(p, text_lower) for p in patterns)
            found[step_name] = step_found
            if not step_found:
                missing.append(step_name)

        print(f"\n  Debate steps found:")
        for step, ok in found.items():
            status = "YES" if ok else "MISSING"
            print(f"    {step}: {status}")

        if missing:
            print(f"\n  [FAIL] Missing debate steps: {missing}")
            print(f"\n  --- Raw LLM text (first 2000 chars) ---")
            print(raw_text[:2000])
            print(f"  --- end ---\n")

        self.assertEqual(missing, [],
                         f"LLM skipped debate steps: {missing}")

        # Also verify JSON was parseable
        self.assertIsNotNone(parsed, "JSON parsing failed on debate response")
        print(f"\n  Final decision: {parsed['action']} "
              f"(strength={parsed.get('signal_strength')}, "
              f"bull={parsed.get('bull_conviction')}, "
              f"bear={parsed.get('bear_conviction')})")

    def test_bull_case_actually_argues_long(self):
        """The BULL CASE section should contain bullish arguments."""
        candles = make_realistic_candles(60, base_price=100000, trend=-40, seed=200)

        print("\n[BULL ARGUMENT TEST] Bearish data — checking bull case still argues long...")
        raw_text, parsed, tokens = self._get_raw_llm_response(
            candles, "ETH/USDT", "4h"
        )

        # Extract the bull case section
        bull_match = re.search(
            r"(?:step\s*4|bull\s*case)[^\n]*\n(.*?)(?:step\s*5|bear\s*case)",
            raw_text, re.DOTALL | re.IGNORECASE
        )

        self.assertIsNotNone(bull_match,
                             "Could not find BULL CASE section in LLM output")

        bull_text = bull_match.group(1).strip()
        print(f"  Bull case section ({len(bull_text)} chars):")
        print(f"    {bull_text[:300]}")

        # Bull case should mention bullish things even in a downtrend
        bullish_terms = ["support", "bounce", "oversold", "reversal", "buy",
                         "upside", "recovery", "accumulation", "demand",
                         "opportunity", "discount", "long", "potential"]
        found_bullish = [t for t in bullish_terms if t in bull_text.lower()]
        print(f"  Bullish terms found: {found_bullish}")

        self.assertGreater(len(found_bullish), 0,
                           "Bull case section has no bullish arguments — "
                           "debate is not genuine")

    def test_bear_case_actually_argues_short(self):
        """The BEAR CASE section should contain bearish arguments."""
        candles = make_realistic_candles(60, base_price=100000, trend=60, seed=300)

        print("\n[BEAR ARGUMENT TEST] Bullish data — checking bear case still argues short...")
        raw_text, parsed, tokens = self._get_raw_llm_response(
            candles, "BTC/USDT", "1h"
        )

        bear_match = re.search(
            r"(?:step\s*5|bear\s*case)[^\n]*\n(.*?)(?:step\s*6|regime\s*check)",
            raw_text, re.DOTALL | re.IGNORECASE
        )

        self.assertIsNotNone(bear_match,
                             "Could not find BEAR CASE section in LLM output")

        bear_text = bear_match.group(1).strip()
        print(f"  Bear case section ({len(bear_text)} chars):")
        print(f"    {bear_text[:300]}")

        bearish_terms = ["resistance", "overbought", "pullback", "correction",
                         "sell", "downside", "rejection", "exhaustion", "risk",
                         "decline", "short", "weakness", "overextended"]
        found_bearish = [t for t in bearish_terms if t in bear_text.lower()]
        print(f"  Bearish terms found: {found_bearish}")

        self.assertGreater(len(found_bearish), 0,
                           "Bear case section has no bearish arguments — "
                           "debate is not genuine")

    def test_hold_gap_compliance(self):
        """
        Test prompt compliance: if bull/bear gap > 15, action should NOT be HOLD.
        The system prompt says: "If bull and bear are close (within 15 points),
        action should be HOLD."

        This tests the inverse — wide gap should mean BUY or SELL.
        """
        # Very strong uptrend — should produce a clear bull > bear gap
        candles = make_realistic_candles(60, base_price=100000, trend=120, seed=400)

        print("\n[HOLD GAP TEST] Strong uptrend — expecting BUY, not HOLD...")
        raw_text, parsed, tokens = self._get_raw_llm_response(
            candles, "BTC/USDT", "1h"
        )

        self.assertIsNotNone(parsed)

        bull = parsed.get("bull_conviction", 50)
        bear = parsed.get("bear_conviction", 50)
        action = parsed.get("action", "HOLD")
        gap = abs(bull - bear)

        print(f"  Action: {action} | Bull: {bull} Bear: {bear} Gap: {gap}")

        if action == "HOLD" and gap > 15:
            print(f"  [PROMPT VIOLATION] HOLD with gap={gap} violates "
                  f"the '<15 points' rule in system prompt")
            # Don't hard-fail, but flag it clearly
            self.fail(
                f"Prompt compliance issue: LLM returned HOLD with bull/bear "
                f"gap={gap} (rule says HOLD only when gap < 15). "
                f"Bull={bull}, Bear={bear}. "
                f"Consider strengthening the prompt enforcement."
            )
        else:
            print(f"  [OK] Action={action} with gap={gap} — prompt compliant")


if __name__ == "__main__":
    unittest.main(verbosity=2)
