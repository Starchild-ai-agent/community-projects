# X Cleaner

A Chrome/Edge MV3 extension that collapses posts on `x.com` / `twitter.com` from:

1. Users who have blocked you (multilingual phrase match on "This post is unavailable" / "您已被屏蔽" etc.).
2. Known AI reply bots (Grok, AskPerplexity, ReplyGuy clones — curated list + regex patterns).
3. AI-style auto-replies (display name like "AI agent" / "powered by GPT" + reply context).

Matches collapse in place with a banner and a **Show** button. Nothing is actually blocked at the account level — purely local hiding, fully reversible, no API risk.

## What

- MV3 manifest, only `storage` + host permissions for x.com / twitter.com.
- Content script + MutationObserver — handles X's virtual scroller.
- Popup with per-filter toggles, allowlist, and a daily counter.
- All rules live in `src/extension/rules.js` (handles, regex, locale phrases).

## Required env

None.

## How to start

```bash
# Build: copy src/extension/ → output/x-cleaner/ + zip it
python src/build.py
```

Then in your browser:

1. Open `chrome://extensions` (or `edge://extensions`).
2. Toggle **Developer mode** on (top right).
3. Click **Load unpacked** → select `output/x-cleaner/`.
4. Pin the extension. Reload `x.com`.

## Outputs

- `output/x-cleaner/` — unpacked extension (load this in Developer mode).
- `output/x-cleaner.zip` — zipped distributable.

## Customizing

| Want to | Edit |
|---|---|
| Add a known bot handle | `src/extension/rules.js` → `AI_HANDLES` (lowercase, no `@`) |
| Add a regex pattern for a bot family | `src/extension/rules.js` → `AI_HANDLE_PATTERNS` (anchor with `^...$`) |
| Add a localized "blocked you" phrase | `src/extension/rules.js` → `BLOCKED_BY_PHRASES` |
| Allowlist a specific account | Use the popup — no code change |

After editing, re-run `python src/build.py` and click the refresh button on the extension card in `chrome://extensions`, then reload `x.com`.

## Troubleshooting

- **Nothing is hidden** — open `chrome://extensions`, make sure X Cleaner is enabled, then click the popup icon and confirm the master toggle is on.
- **A real friend got hidden** — add their handle to the Allowlist in the popup (no rebuild needed). If a regex is the cause, tighten it in `rules.js` and rebuild.
- **A known bot leaks through** — add its handle to `AI_HANDLES`, rebuild, refresh the extension and `x.com`.
- **After an X redesign, detection breaks** — first thing to check is `[data-testid="User-Name"]` in DevTools. X has renamed this selector once or twice historically. Update `getAuthorHandle()` in `src/extension/content.js`.

## Roadmap

- Phase 2 — heuristic scorer for generic spam / engagement bots with a sensitivity slider.
- Phase 3 — local stats dashboard (top hidden patterns, "review last 50 hidden" mode).
- Firefox port — manifest tweaks only; `chrome.*` APIs map to `browser.*`.
