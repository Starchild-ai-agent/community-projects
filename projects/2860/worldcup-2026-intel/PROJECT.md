# WC 2026 Market Desk — Phase 3

Complete 48-team information advantage engine for the 2026 FIFA World Cup.

## What it is

A static HTML/JS dashboard that aggregates real match data, climate impact, historical records, travel/rest analysis, and edge calculations for all 48 qualified teams. Designed for pre-tournament research and paper trading validation.

## Required env

None. Pure client-side + local JSON files.

## How to start

```bash
cd worldcup-2026-intel
python -m http.server 9120
# Open http://localhost:9120
```

Or use the Starchild preview system (already running at port 9082).

## Outputs

- 3-column table view with market % and edge
- Group cards with all 48 teams
- Schedule view with climate scores and rest days
- H2H drawer for every team
- Recent form (10 matches) for all teams
- Historical WC performance (appearances, best finish, last result)
- Climate impact scoring (altitude, temperature, humidity deltas)
- Final group stage standings (all 72 matches with scores)

## Data sources

- `data/matches.json` — 72 group stage fixtures with CET times
- `data/group_standings.json` — Final results + tables for Groups A–L
- `data/historical_wc.json` — WC history for all 48 teams (Wikipedia)
- `data/venues.json` — 15 stadiums with altitude, climate, capacity
- `data/travel_impact.json` — Travel km, rest days, climate scores
- `data/climate_impact.json` — Per-match climate risk flags
- `data/head_to_head.json` — H2H records for priority teams
- `data/recent_form.json` — Last 10 matches per team
- `data/squads.json` + `data/players.json` — Depth charts (8 priority teams)

## Troubleshooting

- Data not loading → Hard refresh (Ctrl+Shift+R) and check browser console
- Preview 404 → Restart with `preview(action='serve')`
- GitHub push fails → Ensure `project.yaml` exists and `open_source()` is called from the skill

## License

MIT (community open source)