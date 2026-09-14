#!/usr/bin/env python3
"""cron_tool.py — validate, describe, and schedule-check cron expressions.

Zero dependencies (stdlib only). Vixie-cron semantics:
5 fields (min hour dom month dow), `*`, lists, ranges, steps, month/dow names,
day-of-week 7==Sunday, and the dom/dow OR rule when both are restricted.

Usage:
  python3 cron_tool.py describe '*/15 9-17 * * 1-5'
  python3 cron_tool.py next '0 9 * * 1-5' --tz Asia/Shanghai -n 5
  python3 cron_tool.py convert '0 9 * * 1-5' --tz Asia/Hong_Kong
  python3 cron_tool.py validate '0 0 * *'
Exit codes: 0 valid, 1 invalid expression.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

FIELDS = [
    ("minute", 0, 59, ["jan"]),
    ("hour", 0, 23, ["jan"]),
    ("day-of-month", 1, 31, ["jan"]),
    ("month", 1, 12, ["jan", "feb", "mar", "apr", "may", "jun",
                      "jul", "aug", "sep", "oct", "nov", "dec"]),
    ("day-of-week", 0, 6, ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]),
]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]
DOW_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


class CronError(ValueError):
    pass


def _resolve(token, fmin, names, fname):
    t = token.strip().lower()
    if re.fullmatch(r"\d+", t):
        n = int(t)
        if fname == "day-of-week" and n == 7:
            return 0
        return n
    if names:
        try:
            i = names.index(t[:3])
        except ValueError:
            raise CronError(f'unknown value "{t}" in {fname}')
        return i + 1 if fmin == 1 else i
    raise CronError(f'unknown value "{t}" in {fname}')


def parse_field(tok, idx):
    fname, fmin, fmax, names = FIELDS[idx]
    if tok is None or tok == "":
        raise CronError(f"missing {fname} field (need 5 fields: minute hour dom month dow)")
    vals = set()
    parts = tok.split(",")
    if parts.count("") > 0:
        raise CronError(f'empty list item in {fname} ("{tok}")')
    for part in parts:
        step = 1
        base = part
        if "/" in part:
            base, _, step_s = part.partition("/")
            if not re.fullmatch(r"\d+", step_s) or int(step_s) < 1:
                raise CronError(f'invalid step "/{step_s}" in {fname}')
            step = int(step_s)
        lo, hi = fmin, fmax
        if base not in ("*", ""):
            pieces = base.split("-")
            if len(pieces) > 2:
                raise CronError(f'invalid range "{base}" in {fname}')
            lo = _resolve(pieces[0], fmin, names, fname)
            hi = _resolve(pieces[1], fmin, names, fname) if len(pieces) == 2 else (fmax if "/" in part else lo)
            if lo < fmin or hi > fmax:
                raise CronError(f"{fname} value out of range {fmin}-{fmax}")
            if lo > hi:
                raise CronError(f'backwards range "{base}" in {fname}')
        elif "/" not in part:
            hi = fmax
        if part == "*":
            vals.update(range(fmin, fmax + 1))
        else:
            vals.update(range(lo, hi + 1, step))
        if "/" in part and base == "*":
            vals = {v for v in vals if (v - fmin) % step == 0}
    return sorted(vals)


def parse(expr):
    toks = re.split(r"\s+", expr.strip())
    if len(toks) != 5:
        raise CronError(f"expected 5 fields, got {len(toks)} (format: minute hour dom month dow)")
    return [parse_field(t, i) for i, t in enumerate(toks)]


def _label(vals, names):
    if len(vals) == 1:
        return names[vals[0]]
    return ", ".join(names[v] for v in vals[:8]) + ("…" if len(vals) > 8 else "")


def describe(expr):
    p = parse(expr)
    mins, hrs, doms, mons, dows = p
    if len(mins) == 60 and len(hrs) == 24:
        head = "Every minute"
    elif len(hrs) == 24 and len(mins) > 1 and all(mins[i + 1] - mins[i] == mins[1] - mins[0] for i in range(len(mins) - 1)):
        head = f"Every {mins[1] - mins[0]} minutes"
    elif len(hrs) == 24:
        head = f"At minute {mins[0]} of every hour"
    elif len(mins) == 1 and len(hrs) == 1:
        head = f"At {hrs[0]:02d}:{mins[0]:02d}"
    else:
        head = "At :" + ", :".join(f"{m:02d}" for m in mins[:6]) + ("…" if len(mins) > 6 else "") + f" past hour(s) {_label(hrs, [str(h) for h in range(24)])}"
    tail = []
    if len(doms) < 31:
        tail.append(f"day of month {_label(doms, [str(d) for d in range(32)])}")
    if len(mons) < 12:
        tail.append(f"in {len(mons)} month(s): {_label(mons, [''] + MONTH_NAMES)}")
    if len(dows) < 7:
        tail.append(f"on {_label(dows, DOW_NAMES)}")
    note = " (dom and dow both restricted — vixie-cron OR rule applies)" if len(doms) < 31 and len(dows) < 7 else ""
    return head + (", " + ", ".join(tail) if tail else "") + note + "."


def _match(p, dt):
    mins, hrs, doms, mons, dows = p
    if dt.minute not in mins or dt.hour not in hrs or dt.month not in mons:
        return False
    dom_ok = dt.day in doms
    dow_ok = dt.isoweekday() % 7 in dows
    both_restricted = len(doms) < 31 and len(dows) < 7
    return (dom_ok or dow_ok) if both_restricted else (dom_ok if len(doms) < 31 else dow_ok if len(dows) < 7 else True)


def next_runs(expr, tz="UTC", count=5, from_dt=None):
    p = parse(expr)
    if ZoneInfo is None:
        raise CronError("zoneinfo unavailable")
    zone = ZoneInfo(tz)
    start = from_dt or datetime.now(zone)
    start = start.replace(second=0, microsecond=0) + timedelta(minutes=1)
    out = []
    cursor = start
    limit = start + timedelta(days=366)
    while len(out) < count and cursor < limit:
        # skip to next month that matches
        if cursor.month not in p[3]:
            y, m = cursor.year, cursor.month
            while (m not in p[3]) and not (y > limit.year or (y == limit.year and m > limit.month)):
                m += 1
                if m > 12:
                    m, y = 1, y + 1
            cursor = cursor.replace(year=y, month=m, day=1, hour=0, minute=0)
            continue
        if _match(p, cursor):
            out.append(cursor)
        cursor += timedelta(minutes=1)
    return out


def convert(expr, tz):
    """Explain a local-time cron expression's UTC equivalent for schedulers that run in UTC."""
    p = parse(expr)
    if len(p[1]) == 24 and len(p[0]) == 60:
        return "Runs every minute — timezone is irrelevant."
    runs = next_runs(expr, tz=tz, count=3)
    utc_hours = sorted({r.astimezone(timezone.utc).hour for r in runs})
    utc_mins = sorted({r.astimezone(timezone.utc).minute for r in runs})
    offs = {(r.utcoffset().total_seconds() / 3600) for r in runs}
    if len(offs) > 1:
        return (f"⚠️ {tz} crosses a DST transition within the sampled window "
                f"(offsets seen: {sorted(offs)}h). Re-convert after the DST change.")
    off = offs.pop()
    sign = "+" if off >= 0 else "−"
    ah = abs(off)
    off_s = f"UTC{sign}{int(ah)}" + (f":{int((ah % 1) * 60):02d}" if ah % 1 else "")
    local_h = sorted({r.hour for r in runs})
    local_m = sorted({r.minute for r in runs})
    return (f"Local {tz} (UTC offset {off_s}): fires at "
            f"{', '.join(f'{h:02d}:{m:02d}' for h in local_h for m in ([local_m[0]] if len(local_m) == 1 else local_m))[:1]}… "
            f"→ same instants in UTC land at hour(s) {utc_hours}, minute(s) {utc_mins}. "
            f"A platform cron that runs in UTC needs hour field {utc_hours} "
            f"minute field {utc_mins} for the SAME wall-clock effect in {tz}.")


def main():
    ap = argparse.ArgumentParser(description="cron expression toolkit (vixie-cron semantics)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("describe"); d.add_argument("expr")
    v = sub.add_parser("validate"); v.add_argument("expr")
    n = sub.add_parser("next"); n.add_argument("expr"); n.add_argument("--tz", default="UTC"); n.add_argument("-n", type=int, default=5)
    c = sub.add_parser("convert"); c.add_argument("expr"); c.add_argument("--tz", required=True)
    args = ap.parse_args()
    try:
        if args.cmd == "describe":
            print(describe(args.expr))
        elif args.cmd == "validate":
            describe(args.expr); print("OK")
        elif args.cmd == "next":
            runs = next_runs(args.expr, tz=args.tz, count=args.n)
            for r in runs:
                print(r.strftime("%Y-%m-%d %H:%M %Z"))
            if not runs:
                print("no runs within 366 days")
        elif args.cmd == "convert":
            print(convert(args.expr, args.tz))
    except CronError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
