# SEC 13F Dashboard (Single-Quarter MVP)

A lightweight, single-file dashboard for exploring institutional holdings reported on **SEC Form 13F**. It aggregates one quarter of 13F filings into a small JSON summary and renders KPI cards + two ECharts bar charts + two tables on a single web page.

![Dashboard](https://raw.githubusercontent.com/Starchild-ai-agent/community-projects/main/.github/placeholder.png)

## What

- **Data source:** [SEC EDGAR Form 13F structured data sets](https://www.sec.gov/dera/data/form-13f) (public, no API key).
- **Coverage:** A single calendar quarter (default: `01jun2025-31aug2025`, ~10,800 filings, ~3.36M holding rows).
- **Output:** Two summary lists pre-computed into `summary.json`:
  - **Top 20 managers** by total reported $value (e.g. Vanguard, BlackRock, State Street).
  - **Top 20 most-widely-held issuers** (by number of distinct funds holding the position).
- **Rendering:** One Flask route serves HTML; `/api/summary` serves the JSON. ECharts is loaded from CDN — no build step.

## Required env

None. The dashboard reads `src/summary.json` directly. To **rebuild** the summary from SEC, the build script makes anonymous HTTPS requests to `www.sec.gov`.

## How to start

Dependencies:

```bash
pip install flask requests
```

Run the dashboard (uses the bundled `summary.json` out of the box):

```bash
cd src
python app.py
```

Then open <http://localhost:8787>.

To rebuild `summary.json` from a fresh SEC quarter:

```bash
cd src
python build_summary.py                       # default quarter
python build_summary.py 01mar2025-31may2025   # custom quarter (must match SEC filename)
```

The build script downloads a ~50–100 MB ZIP from SEC, parses three TSVs, and writes a fresh `summary.json` (~5 KB). Takes 30–90 seconds depending on bandwidth.

## Outputs

- `src/summary.json` — pre-computed aggregates consumed by the dashboard.
- HTTP routes:
  - `GET /` — the HTML dashboard page.
  - `GET /api/summary` — the JSON the page hydrates from.

## Troubleshooting

- **`403 Forbidden` from SEC.** SEC requires a contactable `User-Agent` on every request. Edit the `UA` constant at the top of `build_summary.py` and put a real email there.
- **`KeyError` while parsing TSVs.** SEC occasionally changes column names across quarters. Open the ZIP, inspect the TSV headers, and adjust the field names in `build_summary.py`.
- **Dashboard shows all zeros.** `summary.json` is missing or unreadable. Re-run `python build_summary.py` from inside `src/`.
- **Port 8787 already in use.** Set `PORT=9000 python app.py`.

## Notes

- This is an **MVP**: single quarter, no diffing across quarters, no per-issuer drilldown. Extending it to multi-quarter is straightforward — keep multiple `summary.json` files keyed by quarter slug and add a quarter selector to the page.
- All dollar amounts are in **millions of USD** in the output (SEC reports `VALUE` in thousands; we divide by 1000).
- "Popular holdings" intentionally excludes options (rows where `PUTCALL` is non-empty) to keep the ranking focused on equity positions.
