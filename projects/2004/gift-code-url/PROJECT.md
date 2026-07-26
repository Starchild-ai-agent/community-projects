# gift-code-url

## What

A scan-to-claim page for handing out gift codes at a live event.

Someone scans a QR on a slide, the page assigns them a code, and — the part that
actually matters — the **code is embedded in the signup URL**, so they never type
it. Tap "Sign up", the credit is already attached.

We ran this at a roadshow: 83 scans, 50 codes, 74% redeemed. Embedding the code
in the URL instead of printing it as text to copy was the single biggest UX win.

How it flows:

```
QR  →  claim page  →  POST /api/claim {cid}  →  code assigned
                                              →  https://site/?gift=SC-XXXX-...
```

- **`cid`** is a random UUID stored in `localStorage`. Re-opening the page returns
  the *same* code instead of burning a new one from the pool.
- **Pool exhaustion is a hard stop.** Once every code is out, `/api/claim` returns
  `409 exhausted` and the page shows "All claimed" with a plain signup link. It
  never recycles a code — a recycled code is already redeemed by its first owner
  and would fail at signup, which is worse than being told the cards are gone.
- State lives in `state.json` (`{counter, claims}`), written atomically via
  temp-file + `os.replace`.

Zero dependencies — Python 3 stdlib only.

## Required env

Both are optional; the defaults work out of the box.

| Env | Default | Meaning |
|---|---|---|
| `GIFT_SITE` | `https://iamstarchild.com` | URL prefix the claim link points at |
| `GIFT_PORT` | `9091` | listen port |

You do need a code list. `codes.txt` is gitignored (it holds live codes), so
start from the example:

```bash
cp src/codes.example.txt src/codes.txt
```

One code per line. Only lines starting with `SC-` are loaded, so you can leave
comments in the file.

## How to start

```bash
cp src/codes.example.txt src/codes.txt   # then put your real codes in it
GIFT_SITE=https://your-site.com python3 src/server.py
```

Open `http://localhost:9091/` for the claim page, `/qr` for a printable QR sheet.

## Outputs

| Method | Path | Returns |
|---|---|---|
| GET | `/` | claim page |
| GET | `/qr` | printable QR page |
| GET | `/api/stats` | `{total, claimed}` |
| POST | `/api/claim` | `{code, url, repeat}` · `409 {error:"exhausted"}` when dry |

On disk it writes exactly one file: `src/state.json`, holding the claim counter
and the `cid → code` map. Delete it to reset a run. It is gitignored, along with
`codes.txt`.

## Troubleshooting

**Everyone gets the same code.** Their browsers are sharing a `cid` — usually
because you tested with one device and copied `state.json` around. Delete
`state.json` and reclaim.

**`{"error":"no codes"}`** — `src/codes.txt` is missing or has no line starting
with `SC-`. The example file is `codes.example.txt`; it must be renamed, not
just edited.

**409 exhausted too early.** `claimed` in `/api/stats` counts every unique `cid`,
including your own test hits. Reset with `rm src/state.json` before going live.

**Signup ignores the code.** The link is built in one line of `server.py`:

```python
"url": f"{SITE}/?gift={code}"
```

Change the query parameter to whatever your signup flow reads. Everything else
is generic.

**Port already in use.** `GIFT_PORT=9092 python3 src/server.py`.

## License

MIT.
