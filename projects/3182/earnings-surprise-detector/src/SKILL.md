---
name: earnings-surprise-detector
version: 1.0.0
description: |
  Verify actual quarterly earnings against analyst/research expectations BEFORE acting on a stock recommendation.
  Pulls real 扣非归母净利润同比 / 营收同比 / EPS via mx-data (东方财富), compares to expected growth,
  and gates the recommendation: PASS → proceed, WARN → size down, FAIL → exclude or downweight.
  Use when evaluating any A-share recommendation that cites expected earnings growth, before stating entry prices or position sizing.
  Prevents expensive failures (太辰光 actual -17% vs research +80-120%, 英维克 -82% vs +150%).
author: agentway
tags: [investing, a-shares, earnings, verification, risk-management, mx-data, earnings-surprise]
metadata:
  starchild:
    emoji: "🔍"
    skillKey: earnings-surprise-detector
    requires:
      env: [MX_APIKEY]
      bins: [python3]
    install:
      - kind: pip
        package: openpyxl
user-invocable: true
disable-model-invocation: false
---

# Earnings Surprise Detector

## The problem it solves

You see a research report or hear a thesis: "X will grow earnings 80-120% this quarter." You build a position plan on that number. Then the actual earnings come in at -17%. You're now holding a bag based on a fantasy.

This happened. Multiple times. 太辰光: research said +80-120%, actual was -17%. 英维克: research said +150%, actual was -82%. 欧陆通: research said +180%, actual was a loss.

**The fix is simple: verify before you act.** Pull the actual number from an authoritative source (东方财富 via mx-data), compare to the expectation, and let the gap govern your action.

## When to use

- Any A-share recommendation that cites expected earnings growth (扣非同比, 营收同比, EPS)
- Before stating entry prices, position sizes, or 9-column execution tables
- When a research report or thesis hinges on a specific growth figure
- Before adding to an existing position based on earnings momentum

**Do NOT skip this step.** "The research said X" is not verification. "I pulled the actual number from 东方财富 and it confirms Y" is verification.

## Workflow

### Step 1 — Identify the claim

Extract from the recommendation/thesis:
- **Stock**: name + code (verify code against user's exact text — never auto-correct tickers)
- **Expected growth**: the specific number/range cited (e.g., "扣非同比 +80-120%")
- **Period**: which quarter/year the expectation refers to
- **Source**: who made the expectation (research report, analyst consensus, agent's own analysis)

If no specific growth number is cited, the thesis is too vague to verify — flag this and either pin down the number or treat the thesis as ungrounded.

### Step 2 — Pull actuals via mx-data

Run the verification script:

```bash
python3 skills/earnings-surprise-detector/scripts/verify_earnings.py \
  --stock "太辰光" \
  --code 300570 \
  --expected-min 80 \
  --expected-max 120 \
  --metric 扣非归母净利润同比
```

The script calls mx-data (东方财富) to fetch the latest quarterly 扣非归母净利润同比 growth, parses the result, and compares to the expected range.

**Supported metrics:**
- `扣非归母净利润同比` (default — the most important for A-share verification)
- `营收同比`
- `净利润同比`
- `EPS`

**If mx-data API quota exhausted (status=113):** The script will report this. Switch to manual verification — do NOT proceed without actuals. Use the linqi-data skill as a backup source if available.

### Step 3 — Verdict

The script outputs one of three verdicts:

| Verdict | Condition | Action |
|---------|-----------|--------|
| ✅ **PASS** | Actual ≥ expected-min | Proceed with recommendation. Earnings confirm the thesis. |
| ⚠️ **WARN** | Actual is within -20% of expected-min (e.g., expected 80%, actual 65%) | Size down 50%. Thesis partially confirmed but momentum weaker than expected. Recheck thesis logic. |
| ❌ **FAIL** | Actual < expected-min × 0.8 (e.g., expected 80%, actual < 64%) OR actual is negative when positive expected | **Exclude or downweight.** Do not recommend entry. If already holding, reassess immediately. |

**Hard rule:** When verdict is FAIL, do NOT generate entry prices, target prices, or 9-column execution tables. The thesis is broken at the earnings level — no amount of technical analysis fixes that.

### Step 4 — Integrate verdict into output

Every stock recommendation that passed through this skill should include:

```
### Earnings Verification
- Stock: [name] ([code])
- Expected: [metric] [expected range] (source: [research/analyst])
- Actual: [metric] [actual value] (source: 东方财富 via mx-data, [report date])
- Verdict: [PASS/WARN/FAIL]
- Impact on recommendation: [proceed / size down / exclude]
```

If the verdict is FAIL, the recommendation section should state: "Earnings verification FAILED — actual [X]% vs expected [Y]%. Recommendation withdrawn pending thesis re-evaluation."

## Decision framework: what to do when expectations and reality diverge

| Gap | What it usually means | What to do |
|-----|----------------------|------------|
| Actual >> expected | Earnings momentum stronger than consensus | Good signal — but check if it's a one-off (asset sale, tax benefit). If recurring, thesis is underpriced. |
| Actual ≈ expected | Thesis is on track | Proceed normally. |
| Actual slightly below | Momentum fading but direction right | Size down. Watch next quarter closely. |
| Actual significantly below or negative | Thesis is broken at the fundamental level | **Exit/exclude.** Do not "wait for it to recover." The earnings were the thesis. |
| Actual positive but growth decelerating vs prior quarters | Trend peak may be passing | Check if the thesis assumed accelerating growth. If so, size down even if actual > expected-min. |

## Why 扣非归母净利润同比 is the default metric

- **扣非** (excluding non-recurring items): strips out one-off gains (government subsidies, asset sales, fair value changes) that inflate headline numbers
- **归母** (attributable to parent): excludes minority interests — reflects what shareholders actually own
- **同比** (YoY): seasonality-adjusted, comparable across periods

Research reports often cite 净利润同比 (headline) which can be misleading. Always verify on 扣非 basis. If the research cited 净利润同比, pull both and compare — a large gap between 净利润 and 扣非 is itself a red flag (earnings quality issue).

## Common pitfalls

1. **Wrong stock code**: Always verify code + name against user's exact text. 赛微 300456 ≠ 赛维 688418 — different companies, different fundamentals. The script takes both name and code; mismatch is a hard stop.

2. **Wrong period**: Research might cite Q1 2026 expectations but mx-data returns the latest available quarter. Check the report date in the output. If the latest quarter is different from what the expectation refers to, note the mismatch — you may be comparing apples to oranges.

3. **One-off inflators**: If 扣非同比 is strong but 净利润同比 is much stronger, the gap is non-recurring items. The 扣非 number is the real one.

4. **Negative base year**: If the prior year had a loss (negative base), even a small profit produces an astronomical 同比 growth (e.g., -0.01 → +0.01 = +100%). Check if the base was near-zero — if so, the growth % is meaningless and you should look at absolute profit instead.

5. **API quota**: mx-data has daily call limits. If you hit the limit, don't skip verification — switch to linqi-data or note "unverified, do not act."

## Backup: manual verification

If the script fails or mx-data is unavailable, you can verify manually:

```bash
# Pull earnings directly via mx-data CLI
python3 skills/mx-data/mx_data.py "太辰光 扣非归母净利润同比 最新报告期"
```

Read the output, find the 扣非归母净利润同比 value, and compare to expectations yourself. The script just automates this — the principle is the same: **pull the actual number, compare, then act.**

## References

- `references/expected-growth-sources.md` — where to find analyst consensus and research expectations
