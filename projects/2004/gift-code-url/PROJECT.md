# gift-code-url

## What

A scan-to-claim page for handing out gift codes at a live event.

Someone scans a QR on your slide, the page assigns them a code from your pool,
and — the part that actually matters — the **code is embedded in the signup URL**,
so they never type it. They tap "Sign up", the credit is already attached.

We ran this at a roadshow: 83 scans, 50 codes, ~74% redeemed. Putting the code
inside the URL instead of printing it as text to copy was the single biggest
conversion win.

```
QR  →  claim page  →  POST /api/claim {cid}  →  code assigned
                                              →  https://your-site/?gift=SC-XXXX-...
```

- **`cid`** is a random UUID kept in `localStorage`. Re-opening the page returns
  the *same* code instead of burning a new one from the pool.
- **Pool exhaustion is a hard stop.** Once every code is out, `/api/claim` returns
  `409 exhausted` and the page says "All claimed" with a plain signup link. It
  never recycles a code — a recycled code is already redeemed by its first owner
  and fails at signup, which is a worse experience than being told the cards are
  gone.
- **The `/qr` page generates its own QR** from whatever host is serving it, so
  the same file works on localhost, a tunnel, or production with no edit.
- State lives in `state.json` (`{counter, claims}`), written atomically.

Zero dependencies — Python 3 stdlib only, plus one vendored MIT QR encoder.

## Loading your gift codes

This is the only setup step that matters, so in detail.

**1. Get the codes from your issuer.** On Starchild that's the Credits / Gift Card
page — buy a batch and copy the code list it gives you. Any issuer works; the
server treats codes as opaque strings.

**2. Create the pool file.**

```bash
cp src/codes.example.txt src/codes.txt
```

**3. Paste your codes in, one per line.**

```
SC-7K2M-9QX4-LP31
SC-A8ND-3BVE-2RTY
SC-QW5J-8HDC-6FKZ
```

Rules the loader follows:

- Only lines starting with the prefix (default `SC-`) are loaded. Everything else
  — blank lines, `#` comments, your own notes — is ignored, so you can annotate
  the file freely.
- **Duplicates are dropped automatically.** A copy-paste slip can't hand the same
  code to two people.
- Codes are handed out **top to bottom**, in file order.
- Different prefix? Set `GIFT_PREFIX=GIFT-` (or whatever) and the loader follows it.

**4. Adding more codes mid-event.** Just append to the bottom of `codes.txt`. The
file is re-read on every claim, so new codes go live immediately with no restart
and nobody loses their assignment. **Never reorder or delete existing lines** —
the claim counter maps to line positions, so editing the middle of the file
reassigns codes people already hold.

**5. Resetting between events.** `rm src/state.json`. That clears the counter and
the `cid → code` map; every visitor gets a fresh code from the top.

`codes.txt` and `state.json` are both gitignored — live codes and visitor IDs
never end up in a commit.

## Required env

All optional; defaults work out of the box.

| Env | Default | Meaning |
|---|---|---|
| `GIFT_SITE` | `https://iamstarchild.com` | URL prefix the claim link points at |
| `GIFT_PORT` | `9091` | listen port |
| `GIFT_PREFIX` | `SC-` | lines in `codes.txt` starting with this are codes |

## How to start

```bash
cp src/codes.example.txt src/codes.txt   # then paste your real codes in
GIFT_SITE=https://your-site.com python3 src/server.py
```

- `http://localhost:9091/` — the claim page attendees land on
- `http://localhost:9091/qr` — the QR page you put on the projector

Expose it publicly (your own host, a tunnel, or a platform preview URL) and point
your slide at that address.

## Outputs

| Method | Path | Returns |
|---|---|---|
| GET | `/` | claim page |
| GET | `/qr` | projector QR page with a live "N of M left" counter |
| GET | `/api/stats` | `{total, claimed}` |
| POST | `/api/claim` | `{code, url, repeat}` · `409 {error:"exhausted"}` when dry |

On disk it writes exactly one file, `src/state.json`.

## Troubleshooting

**`{"error":"no codes"}`** — `src/codes.txt` is missing, or no line starts with
the prefix. `codes.example.txt` must be *copied to* `codes.txt`, not just edited.

**Everyone gets the same code.** Their browsers share a `cid` — usually because
you copied a `state.json` between machines. Delete it and reclaim.

**409 exhausted too early.** `claimed` in `/api/stats` counts every unique `cid`,
including your own test hits. `rm src/state.json` before going live.

**Signup ignores the code.** The link is built in one line of `server.py`:

```python
"url": f"{SITE}/?gift={code}"
```

Change the query parameter to whatever your signup flow reads. Everything else is
generic.

**QR points at localhost.** It encodes the host serving `/qr`. Open the page via
the public URL, or override with `/qr?url=https://your-public-domain.com`.

**Port already in use.** `GIFT_PORT=9092 python3 src/server.py`.

## Give this to your agent

Paste this into any coding agent to get the service running:

> Clone `https://github.com/Starchild-ai-agent/community-projects` and use
> `projects/2004/gift-code-url`. It's a zero-dependency Python 3 stdlib service
> that hands out gift codes at events: a visitor scans a QR, gets one unique code
> from a pool, and the code is embedded in the signup URL so they never type it.
> Set it up for me: copy `src/codes.example.txt` to `src/codes.txt`, ask me to
> paste my gift codes in (one per line, only lines starting with `SC-` are read,
> duplicates ignored, handed out top to bottom), then start it with
> `GIFT_SITE=<my signup URL> python3 src/server.py`. Serve it on a public URL and
> give me two links: `/` for attendees and `/qr` for the projector. Confirm the
> pool size via `/api/stats` before we go live, and tell me how to append more
> codes mid-event without restarting.

## License

MIT. Bundled QR encoder: qrcode-generator by Kazuhiko Arase, MIT.
