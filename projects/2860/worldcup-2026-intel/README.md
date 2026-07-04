# worldcup-2026-intel

**Information advantage layer for the 2026 FIFA World Cup.**

Public, source-linked intelligence on all 48 teams — squad depth, travel/rest, climate impact, head-to-head, injuries, recent form, venue data. Built before any paper trading or edge calculation.

**Mandate:** Information first. Paper trading second. No live capital until 30–50 documented paper trades with validated edge.

---

## Current Status (June 2026)

**Phase 1 — Information Layer: COMPLETE**

- 48 teams with market % (locked)
- 72 group stage matches with dates, CET times, venues, cities
- Recent form (5–7 matches per team) with sources
- Squad depth + injuries for all 48 teams
- Venues with climate, altitude, humidity (15 stadiums)
- Head-to-head records for all priority rivalries
- Key players + injuries (11-man XI + bench + flags for 8 priority teams)
- Travel impact + rest days + climate warnings (group stage)

**Phase 2 — Information Advantage Engine: IN PROGRESS**

- Travel/rest/climate impact engine (group stage)
- Risk flags: HIGH_TRAVEL, LOW_REST, CLIMATE_RISK, ALTITUDE

---

## Data Files (`/data/`)

| File | Description | Status |
|------|-------------|--------|
| `groups.json` | 48 teams, groups, market % | ✅ |
| `matches.json` | 72 group stage matches + CET + venues | ✅ |
| `recent_form.json` | 5–7 recent matches per team, sources | ✅ |
| `squads.json` | Depth, starters, bench, injuries, strength area | ✅ |
| `venues.json` | Climate, altitude, humidity, notes (15 stadiums) | ✅ |
| `head_to_head.json` | Historical matchups for priority teams | ✅ |
| `players.json` | 11-man XI + injuries + bench (8 priority teams) | ✅ |
| `travel_impact.json` | Travel km, rest days, climate scores, risk flags | ✅ |
| `historical.json` | WC record, best finish, appearances | ✅ |

All data is sourced. Every entry includes `source` + `url` where applicable.

---

## Project Structure

```
worldcup-2026-intel/
├── index.html
├── style.css
├── app.js
├── data/
│   ├── groups.json
│   ├── matches.json
│   ├── recent_form.json
│   ├── squads.json
│   ├── venues.json
│   ├── head_to_head.json
│   ├── players.json
│   ├── travel_impact.json
│   └── historical.json
├── scripts/
├── plan.md
├── RULES.md
├── README.md
└── .gitignore
```

---

## Philosophy

- **Real data > narratives.** Every claim needs evidence.
- **Source-first.** Clickable links on every data point.
- **Paper before live.** 30–50 logged paper trades minimum before any real capital.
- **Additive only.** Never break existing rendering.
- **All 48 teams.** No gating behind "priority only."

---

## Phases

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Information Layer (data aggregation) | ✅ Complete |
| 2 | Information Advantage Engine (travel, climate, style) | 🔄 In progress |
| 3 | Edge Calculation Layer (probabilities vs market) | ⏳ Pending |
| 4 | Paper Trading Validation (30–50 logged trades) | ⏳ Pending |

**No live capital until Phase 4 passes.**

---

## License / Use

Public for now. Data sourced from Wikipedia, Transfermarkt, CONCACAF, UEFA, national FAs, and official tournament records. Verify before any trading use.

---

**Built as a real, auditable project. Information advantage first.**
