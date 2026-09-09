# Market Opening Checklist (Weekly)

A self-contained, static HTML service UI for preparing a market-opening review. It
enforces the core discipline of the `market-opening-checklist` skill: record observable
**Facts** first, then — and only then — write **Analysis**. Nothing is fetched from the
network; every value is typed in by the user from their own live data sources.

## What

- **Facts section** — 10 observable pre-market items (overnight futures, pre-market
  movers, economic calendar, earnings, Treasury yields, FX/DXY, commodities, VIX,
  insider filings, sector rotation). Each item is a checkbox plus a short text field
  for the observed value.
- **Analysis section** — 7 interpretation items (market bias, support/resistance, top
  catalysts, invalidation risks, conviction setups, positioning adjustments, first-30-min
  scenarios). Unlocked for editing only after all Facts items are checked.
- **Session date** — a date field that defaults to today via browser JavaScript.
- **Progress indicator** — a bar plus `x / 17` counter covering all checklist items.
- **Reset button** — clears the current session's state (with confirmation).
- **Persistence** — state is saved per session date in `localStorage` under the key
  `market-opening-checklist-weekly:v1`. Switching the date loads that day's state.

## Required env

None. The project runs entirely in the browser — no backend, no API keys, no network
calls. `.env.example` is included for convention only.

## How to start

Open `src/index.html` directly in a modern browser, or serve the directory statically:

```bash
cd output/projects/market-opening-checklist-weekly
python3 -m http.server 8787
# then visit http://localhost:8787/src/index.html
```

## Usage

1. Set the session date (defaults to today).
2. Work through the **Facts** section, populating each value from live or near-live
   sources (exchange feeds, futures, news wires). Check each item as it is recorded.
3. Once all Facts are checked, the **Analysis** section unlocks. Record interpretation,
   risk assessment, and scenarios there — never mix the two.
4. Progress bar and counter update as you go; state auto-saves to `localStorage`.
5. Use **Reset session** to clear the current date's state and start over.

## Outputs

- **Static checklist UI** (`src/index.html`) — a single, self-contained HTML page with
  the Facts/Analysis checklist, session date picker, and reset control. No build step.
- **Browser-local persistence** — session state is stored only in the browser's
  `localStorage` (key `market-opening-checklist-weekly:v1`), keyed by session date;
  nothing is written to a server.
- **Progress indicator** — an always-visible bar and `x / 17` counter reflecting
  completion of all checklist items.
- **No live data** — the UI fetches nothing; every market value is typed in by the user,
  so output state is only what you enter.

## Sources

- Checklist structure and Facts/Analysis separation: `skills/market-opening-checklist/SKILL.md`.
- Project packaging conventions (`project.yaml`, publisher block, `.env.example`,
  `.gitignore`, static `src/index.html` entry): `skills/community-publish/SKILL.md`
  and existing projects under `output/projects/`.

## Troubleshooting

- **Checklist state disappeared** — state is keyed by session date and stored in
  `localStorage`. Private/incognito windows or cleared site data wipe it; pick the
  correct date or re-enter values.
- **Analysis section stays locked** — it unlocks only when every Facts item is checked.
  Verify all 10 Facts checkboxes are ticked for the selected date.
- **Date does not default to today** — JavaScript may be disabled, or the page was
  opened from a `file://` context that blocks storage. Serve over HTTP or enable JS.
- **Progress bar not updating** — hard-refresh the page; if it persists, clear site
  data for this origin and start a fresh session.

This project is a preparation aid and is not financial advice. It ships with empty
fields and fetches no data — all market values must come from your own live sources.
