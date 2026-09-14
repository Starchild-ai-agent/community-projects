---
name: cron-studio
description: Validate, describe, and schedule-check cron expressions with a zero-dependency CLI. Use when the user mentions cron, crontab, scheduled tasks, "every 15 minutes", timezone conversion for schedulers, or asks when a cron will next fire. Vixie-cron semantics (5 fields, lists/ranges/steps, names, dom/dow OR rule, dow 7==Sunday).
---

# Cron Studio

Stdlib-only CLI that makes cron expressions machine-checkable and human-readable.
Script: `scripts/cron_tool.py` (no pip installs, no network).

## When to use

- User asks "what does `0 */6 * * *` mean" or "when will this cron fire next"
- Registering/updating a `scheduled_task` whose cron runs in **UTC** but the user
  thinks in local time — use `convert` to get the UTC hour/minute fields
- Debugging "my cron never fires" — validate field ranges and the dom/dow OR rule
- Any statement about cron semantics that must be verified, not guessed

## Commands

```bash
# Human-readable description (also validates; exit 1 + INVALID message on error)
python3 skills/cron-studio/scripts/cron_tool.py describe '*/15 9-17 * * 1-5'

# Just validate (exit code 0/1) — safe to run before installing a schedule
python3 skills/cron-studio/scripts/cron_tool.py validate '0 9 * * 1-5'

# Next N fire times in any IANA timezone
python3 skills/cron-studio/scripts/cron_tool.py next '0 9 * * 1-5' --tz Asia/Shanghai -n 5

# Local → UTC conversion for platform schedulers that run in UTC
python3 skills/cron-studio/scripts/cron_tool.py convert '0 9 * * 1-5' --tz Asia/Hong_Kong
```

## Semantics implemented (vixie-cron)

- 5 fields: minute hour day-of-month month day-of-week
- `*`, lists `1,15,30`, ranges `9-17`, steps `*/5` and `5-20/3`
- Month names `jan-dec`, dow names `sun-sat`, dow `7` == Sunday
- **dom/dow OR rule**: if BOTH are restricted, a time matching either fires
- Rejects out-of-range values, backwards ranges, step 0, wrong field count
- DST-aware `next`/`convert` via `zoneinfo` (convert warns if a DST transition
  falls inside the sampled window)

## Workflow for scheduled tasks

1. User says "every weekday 9am HKT" → build `'0 9 * * 1-5'`
2. `convert '0 9 * * 1-5' --tz Asia/Hong_Kong` → returns the UTC hour/minute
3. Use those UTC fields in `scheduled_task` (cron is UTC on this platform)
4. Sanity-check with `next --tz Asia/Shanghai -n 3` to show the user real dates

## Companions

- Web UI (build/decode in browser, no install): Cron Studio project —
  output/projects/cron-studio/index.html, published as
  `6171-cron-studio-build-decode-cron`
- Platform scheduling: `scheduled_task` tool (cron strings are UTC)

## Gotchas

- `cron_tool.py convert` prints the UTC **hour/minute field values**, not a new
  full expression — assemble the expression yourself with `*` in dom/month/dow
  unless day-of-month/week were restricted.
- Month/day names are case-insensitive 3-letter prefixes (`JAN`, `Sun`).
- `describe` output is for humans; for assertions parse `next` timestamps instead.
