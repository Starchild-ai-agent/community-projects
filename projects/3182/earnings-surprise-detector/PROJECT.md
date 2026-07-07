# Earnings Surprise Detector

## What

Verify actual quarterly earnings against analyst/research expectations BEFORE acting on a stock recommendation. Pulls real 扣非归母净利润同比 / 营收同比 / EPS via mx-data (东方财富权威数据), compares to the expected growth range, and gates the recommendation:

- ✅ **PASS** — actual ≥ expected → proceed with recommendation
- ⚠️ **WARN** — actual slightly below → size down 50%
- ❌ **FAIL** — actual significantly below or negative → exclude, do not recommend entry

**Why this exists:** Acting on unverified research expectations is expensive. Documented failures:
- 太辰光: research said +80-120%, actual was -17% (~100pp gap)
- 英维克: research said +150%, actual was -82% (~230pp gap)
- 欧陆通: research said +180%, actual was a loss (>180pp gap)

In every case, the agent trusted research reports without pulling actuals. This skill makes verification mechanical: always pull, always compare, then act.

## Required env

| Variable | Description |
|----------|-------------|
| `MX_APIKEY` | 东方财富妙想 API key. Get it from https://dl.dfcfs.com/m/itc4 |

## How to start

```bash
# Install dependency
pip install openpyxl

# Set API key
export MX_APIKEY=your_key_here

# Run verification
python3 scripts/verify_earnings.py \
  --stock "太辰光" \
  --code 300570 \
  --expected-min 80 \
  --expected-max 120 \
  --metric 扣非归母净利润同比
```

Exit codes: `0` = PASS, `1` = WARN, `2` = FAIL

## Outputs

- **stdout**: Human-readable verdict report + JSON output
- **JSON fields**: stock, code, metric, expected_min, expected_max, actual, report_date, source, verdict, reason, action

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `MX_APIKEY not set` | Env var missing | Export MX_APIKEY or add to workspace/.env |
| `mx-data API quota exhausted` | Daily call limit reached | Use linqi-data skill as backup, or wait for quota reset |
| `Could not parse mx-data output` | API response format changed | Run `python3 skills/mx-data/mx_data.py "太辰光 扣非归母净利润同比"` manually to inspect raw output |
| `No numeric values found` | Data not available for this stock/period | Try a different metric or check if the stock has recent earnings reports |
