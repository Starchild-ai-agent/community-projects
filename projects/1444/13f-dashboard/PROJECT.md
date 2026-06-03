## What
13F Atlas is an interactive dashboard for SEC Form 13F filings. It aggregates institutional holdings by manager and quarter, then provides drill-down views for portfolio composition, baseline performance comparison, and quarter-over-quarter holdings diffs.

## Required env
- SEC_USER_AGENT (optional)
- F13_DATA_DIR (optional)

## How to start
- Local service:
  - `python server.py`
- Expected port:
  - `8765`

## Outputs
- HTTP UI served from `static/`
- API endpoints under `/api/*` for funds, periods, holdings, baseline series, and diffs
- On-demand download/update jobs for selected managers from SEC 13F data

## Troubleshooting
- If `/api/funds` is empty, ensure 13F data exists under `F13_DATA_DIR`.
- If SEC requests fail, set a valid `SEC_USER_AGENT` with contact info.
- If chart loads but data is blank, check JSON/CSV files under `output/13f` and retry refresh.
