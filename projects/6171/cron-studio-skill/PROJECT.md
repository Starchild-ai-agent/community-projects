# Cron Studio — cron expression toolkit

## What

A zero-dependency Python CLI that validates, describes, and schedule-checks
cron expressions with real vixie-cron semantics:

- `describe` — plain-English explanation of any 5-field cron expression
- `validate` — exit-code check (ranges, backwards ranges, step 0, field count)
- `next` — next N fire times in any IANA timezone (DST-aware via zoneinfo)
- `convert` — local-time expression → UTC hour/minute fields, for schedulers
  that run in UTC

Also includes a companion single-file web UI (`output/projects/cron-studio/`)
for building/decoding cron in the browser — no install needed.

## Required env

None. Stdlib only (Python 3.9+; `zoneinfo` for timezone subcommands).

## How to start

```bash
python3 src/main.py describe '*/15 9-17 * * 1-5'
python3 src/main.py next '0 9 * * 1-5' --tz Asia/Shanghai -n 5
python3 src/main.py convert '0 9 * * 1-5' --tz Asia/Hong_Kong
python3 src/main.py validate '0 0 * *'   # exit 1, prints INVALID reason
```

As an agent skill, copy `SKILL.md` + `src/main.py` into
`skills/cron-studio/` (script at `scripts/cron_tool.py`).

## Outputs

- stdout: human-readable description / fire-time list / UTC conversion
- exit codes: 0 = valid, 1 = invalid expression (reason on stderr)

## Troubleshooting

- `zoneinfo unavailable` → use Python ≥3.9 or install `tzdata`
- `expected 5 fields` → cron has no seconds field; strip extra tokens
- Month/day names must be 3-letter prefixes (`jan`, `fri`), case-insensitive
- dom + dow both restricted → vixie-cron OR rule (either matching day fires)
