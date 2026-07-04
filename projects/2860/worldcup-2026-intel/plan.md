# World Cup 2026 Market Desk — Phase 3 Plan

**Goal**  
Build a complete, source-linked information advantage engine that covers **all 48 teams** with real data before any paper trading, alerts, or live execution features are added.

**Current State (end of Phase 2.7)**  
- 3-column table view with market % and edge for all 48 teams  
- Team profile drawer (basic)  
- H2H drawer with win rate / GD for all teams  
- Recent form (10 matches + GD) for all teams  
- Key players section (placeholder) for priority 8 teams only  
- Schedule view for all teams  
- Group filter (A–H + ALL) and search working  
- All changes are additive and respect RULES.md  

**Phase 3 Rule**  
No paper trading, no ledger, no alerts, no execution engine until every item in this plan is complete and the information layer feels "really well".

---

## The 10 Steps (All 48 Teams)

| Step | Task | Description | Acceptance Criteria |
|------|------|-------------|---------------------|
| 1 | Historical WC performance | Best finish, appearances, last WC result, notable matches inside every team profile drawer | Visible for all 48 teams, sourced |
| 2 | Squad depth & roster notes | Estimated squad size, key returning players, injury flags | Placeholder first, then real data; all 48 teams |
| 3 | Travel & rest days | Days between matches + rough travel distance on every schedule row | Visible for all 48 teams |
| 4 | Source links everywhere | Every fixture, H2H match, recent form line, historical record has a clickable Wikipedia / ESPN / FIFA / Opta link | 100% coverage, no dead links |
| 5 | Venue & climate notes | Altitude, avg temperature, pitch type, home advantage indicators | Light data, all 48 teams |
| 6 | Key players / top scorers | 3–5 names per team (goals, assists, clean sheets) | Placeholder first, then real data; all 48 teams |
| 7 | H2H matrix view | Compact grid showing win rate vs all opponents at once | New view or modal, works for all teams |
| 8 | Fixture status & polish | Upcoming / Live / Finished badges + consistent date formatting | All schedule rows |
| 9 | Search + filter improvements | Faster search, confederation filter, "has full data" toggle, saved filters | UX polish across table + schedule |
| 10 | Evidence pack export | One-click JSON / Markdown / PDF export of everything known about any team | Works for all 48 teams, clean output |

---

## Constraints & Principles

- **Additive only** — never replace or break existing rendering.
- **Source-first** — every new piece of information must show a visible, clickable source.
- **All 48 teams** — no more gating behind the original 8 REAL_TEAMS list.
- **Data stays in files** — JSON/CSV for now. Database only after Phase 3 if live updates are required.
- **Paper trading deferred** — only considered after Step 10 is signed off.
- **Priority teams (D + L)** still carry the orange "R" badge for visual focus, but features work for everyone.

---

## Recommended Execution Order

1. Step 1 — Historical WC performance (already partially prepared)
2. Step 4 — Source links on every existing drawer and table row (high impact)
3. Step 3 — Travel & rest days (already prepared)
4. Step 2 — Squad depth
5. Step 5 — Venue & climate
6. Step 6 — Key players / top scorers
7. Step 7 — H2H matrix
8. Step 8 — Fixture status badges
9. Step 9 — Search & filter polish
10. Step 10 — Evidence pack export

---

**Next action after this plan is approved:**  
Start Step 1 (Historical WC performance for all 48 teams) with a clean edit.

---

*Plan created: 2026-06-08*  
*Phase 3 — Information advantage engine first*