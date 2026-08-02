# WC 2026 Tournament Archive + Post-Mortem

Closed-tournament archive for the 2026 FIFA World Cup. Spain champions (1-0 AET vs Argentina, 19 Jul 2026, MetLife). Priority desk: Groups D + L.

## What it is

Static HTML/JS desk with:

- Podium + champion path (ARCHIVE)
- Visual knockout bracket R32 → Final (BRACKET)
- Post-mortem signal grades for 8 priority teams (POST-MORTEM)
- Full group results with scores (RESULTS)
- One-click evidence pack export (Markdown)

## Required env

None. Pure client-side + local JSON.

## How to start

```bash
cd worldcup-2026-intel
python -m http.server 9083
# Open http://localhost:9083
```

Or Starchild preview on the configured port.

## Outputs

- Archive podium and priority paths
- Knockout bracket tree + flat KO list
- Post-mortem HIT/MISS/MIXED/N/A grades
- Group cards / table / results / matrix (legacy research views)
- Downloadable evidence packs (`wc2026-evidence-*.md`)

## Data sources

- `data/matches.json` — 72 group matches with scores
- `data/group_standings.json` — final group tables
- `data/knockout_results.json` — full KO tree
- `data/tournament_archive.json` — priority + champion paths
- `data/postmortem.json` — signal grades
- `data/travel_impact.json` / `climate_impact.json` — risk flags
- Sources linked in-app (Yahoo Sports, Wikipedia, FIFA)

## Troubleshooting

- Data not loading → hard refresh (Ctrl+Shift+R), check browser console
- Preview 404 → restart with `preview(action='serve')`
- Export does nothing → allow downloads; open ARCHIVE/BRACKET first so data is loaded

## License

MIT
