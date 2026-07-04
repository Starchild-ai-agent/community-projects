# RULES.md — WC 2026 Market Desk (Information Layer)

**Core Principle**  
Never destroy a working view to add a new feature. Information density is added **on top of** the current structure, never by replacing it.

**Mandatory Rules**

1. **Never delete or replace an existing render function** (`renderTable`, `renderCards`, `renderEdgeTracker`, `renderSchedule`). Only extend or wrap.
2. **Every edit to `app.js` or `index.html` must use `edit_file` with an exact, unique string match**. No large block rewrites.
3. **Before any change that touches layout or data rendering, create a one-line backup comment** in the file: `// BACKUP: renderTable vX - YYYY-MM-DD`.
4. **New views or panels must be added as new hidden `<div id="view-xxx">` blocks**, never by modifying existing view containers.
5. **All new data access must be null-safe**: `if (!fixturesData || !fixturesData[teamName]) return '—';`
6. **Never change the data loading sequence** in `loadData()`. Existing fetches stay exactly as they are.
7. **After every `edit_file` that touches JS, run** `node --check app.js` **before creating a new preview**.
8. **Keep the current preview running** until the new preview is verified working by the user.
9. **Do not change column count or table structure** in the main TABLE without explicit user approval. The current 6-column layout (GRP | TEAM | MARKET % | YOUR PROB | EDGE | NEXT FIXTURE) is frozen.
10. **Any rule violation must be self-reported immediately** with the exact line that broke and the rollback command.

**Enforcement**  
These rules are loaded into my context for every turn on this project. If a step would violate a rule, I must stop and propose a compliant alternative.

**Current Frozen State (2026-06-05)**  
- TABLE: 6 columns, one row per team (48 rows)
- SCHEDULE: 24 matches for D + L
- Data sources: groups.json, fixtures.json (8 teams only), head_to_head.json, recent_form.json

**Step 1 Target (under rules)**  
Enhance the existing "NEXT FIXTURE" column to show up to 3 matches per team using the same cell. No new columns, no structural change.