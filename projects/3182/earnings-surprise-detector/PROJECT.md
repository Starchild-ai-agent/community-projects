# Earnings Surprise Detector 📊

## What

Verify actual quarterly earnings (扣非归母净利润同比/营收同比/EPS) against analyst/research expectations BEFORE acting on a thesis. Prevents building positions on false growth assumptions.

## Why This Exists

Documented failures from trusting research reports without verification:

| Stock | Research Expected | Actual | Gap |
|-------|-------------------|--------|-----|
| 太辰光 (300570) | +80~120% 扣非同比 | -17% | ~100pp |
| 英维克 (002837) | +150% 扣非同比 | -82% | ~230pp |
| 欧陆通 (300870) | +180% 扣非同比 | Loss | >180pp |

**Pattern:** In all cases, the agent trusted research reports without pulling actuals. The fix is mechanical: always verify via mx-data before acting.

## How It Works

```
verify_earnings.py --stock "太辰光" --code 300570 \
    --expected-min 80 --expected-max 120 --metric 扣非归母净利润同比
      │
      ├─ Query mx-data (东方财富) for actual quarterly earnings
      ├─ Compare actual vs. expected range
      ├─ Verdict: PASS (✅) / WARN (⚠️) / FAIL (❌)
      └─ Output JSON with actuals, expected, gap, recommendation
```

## Required env

- `MX_APIKEY` — 妙想/东方财富 API key (set via `request_env_input`)

## How to start

```bash
cd /data/workspace
python3 skills/earnings-surprise-detector/scripts/verify_earnings.py \
    --stock "太辰光" --code 300570 \
    --expected-min 80 --expected-max 120 \
    --metric 扣非归母净利润同比
```

## Outputs

```json
{
  "stock": "太辰光",
  "code": "300570",
  "metric": "扣非归母净利润同比",
  "actual": -17.0,
  "expected_min": 80,
  "expected_max": 120,
  "gap": -97.0,
  "verdict": "FAIL",
  "recommendation": "Do not build position. Actual earnings contradict thesis."
}
```

| Verdict | Condition | Action |
|---------|-----------|--------|
| ✅ PASS | Actual ≥ expected-min | Thesis confirmed, proceed |
| ⚠️ WARN | Actual within 20% below expected-min | Investigate before acting |
| ❌ FAIL | Actual > 20% below expected-min | Stop. Do not build position. |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "MX_APIKEY not set" | Set via `request_env_input` or workspace/.env |
| "mx-data query timed out" | Retry; mx-data has rate limits |
| "调用次数已达上限" | Daily quota exhausted (500/day, resets 00:10) |
| Wrong stock data | Always cross-check code + name against user's exact text |

License: MIT
