# Expected Growth Sources

Where to find analyst consensus and research expectations for A-shares.

## Primary sources

### 1. Research reports (研报)
- **东方财富研报**: https://data.eastmoney.com/report/ — search by stock code, filter by date
- **同花顺研报**: https://stock.10jqka.com.cn/ — analyst consensus estimates
- **Wind / Choice**: institutional terminals (if you have access)

### 2. Analyst consensus (一致预期)
- **东方财富一致预期**: https://data.eastmoney.com/yjyg/ — aggregated analyst forecasts
- Includes: 净利润同比预测, EPS预测, 营收预测
- Usually shows current year + next year estimates

### 3. Company guidance (业绩预告)
- **东方财富业绩预告**: https://data.eastmoney.com/yjyg/ — official company pre-announcements
- These are the company's own forecasts — most reliable before actuals drop
- Watch for 修正公告 (revised guidance) — downward revisions are strong negative signals

## How to extract the expected number

When a research report or thesis cites expected growth:

1. **Identify the exact metric**: Is it 扣非同比, 净利润同比, or 营收同比? They differ significantly.
2. **Identify the period**: Q1? H1? Full year? Which year?
3. **Identify the source**: Single analyst or consensus? Single reports are less reliable.
4. **Note the date**: Was the expectation set before or after recent market events?

## Red flags in expectations

- **Single-source expectations**: One analyst's number is not consensus. Look for at least 3 analysts.
- **Stale expectations**: If the report is >3 months old, the expectation may not reflect recent developments.
- **Round numbers**: "We expect 100% growth" is suspicious. Real analysis gives ranges.
- **No methodology**: If the report doesn't explain HOW they got the number, it's a guess.
- **Headline vs 扣非 gap**: If 净利润同比 >> 扣非同比, the growth is driven by non-recurring items — lower quality.

## Documented failures (why this skill exists)

| Stock | Research Expected | Actual | Gap | Consequence |
|-------|-------------------|--------|-----|-------------|
| 太辰光 (300570) | +80~120% 扣非同比 | -17% | ~100pp | Position built on false growth assumption |
| 英维克 (002837) | +150% 扣非同比 | -82% | ~230pp | Major loss from unverified thesis |
| 欧陆通 (300870) | +180% 扣非同比 | Loss | >180pp | Complete thesis failure |

**Pattern**: In all cases, the agent trusted research reports without pulling actuals. The fix is mechanical: always verify via mx-data before acting.
