# tqx-roadshow-deck

## What

A presentation deck that is just an HTML file.

No React, no build step, no Reveal.js, no `npm install`. Three files and a folder
of assets. Open `src/index.html` in a browser and it works — including offline,
which is the only reason it survived a conference-room wifi outage.

Built for a roadshow talk; the content is TQX/Starchild-specific, but the deck
machinery underneath is the reusable part:

- **8 slides**, arrow keys / click / space to advance
- **Bilingual EN ↔ ZH** toggle — every string has both, switching is instant and
  re-runs the current slide's animations
- **Auto-scaling** — the whole deck is a fixed 16:9 canvas scaled with one CSS
  transform to fit any window, so it looks identical on a laptop and a projector
  without a single media query
- **Animated counters** that tick up when their slide becomes active, and reset
  if you navigate back
- **Canvas starfield** background, parallax tilt on cards
- **Typed-line sequencing** — text reveals line by line, per slide

Why not a framework: a deck is read-only, runs once, on one machine, for twenty
minutes. Every dependency is a thing that can fail in front of an audience. This
one has none.

## Required env

None. It is fully static — no API keys, no backend, no network calls at runtime.

## How to start

```bash
python3 -m http.server 8080 --directory src
```

Then open `http://localhost:8080/`. Or just double-click `src/index.html`.

Keys: `→` / `space` next · `←` back · click anywhere advances · the `EN` / `中`
buttons switch language.

## Outputs

Nothing is written to disk — this is a read-only static page. The only output is
what's on screen.

Files you'll edit to make it yours:

| What | Where |
|---|---|
| Slide content | `src/index.html` — one `<section class="slide">` each |
| EN/ZH strings | `setLang()` in `src/script.js` |
| Per-slide animation timing | `play()` in `src/script.js` |
| Colours, type scale | `:root` variables at the top of `src/styles.css` |

The colour system is six CSS variables. Change `--orange` and the whole deck
re-themes.

## Troubleshooting

**Fonts look different from the screenshots.** The original used Google Sans,
which isn't redistributable, so the `.woff2` files are deliberately *not* in this
repo. The CSS falls back to `'Noto Sans SC', sans-serif` cleanly. Drop your own
files into `src/assets/` and the `@font-face` rules at the top of `styles.css`
pick them up with no other change.

**Blank page when opening the file directly.** Some browsers block `file://`
fetches. Use the `python3 -m http.server` command above instead.

**Slides are cut off or letterboxed.** That's the 16:9 scaler doing its job — the
deck keeps its aspect ratio rather than stretching. Resize the window or go
fullscreen (`F11`).

**Edits to CSS/JS don't show up.** `index.html` loads them with cache-busting
query strings (`styles.css?v=28`). Bump the number or hard-reload
(`Ctrl/Cmd + Shift + R`).

**Animations replay when I go back.** Intended — counters and typed lines reset
so a slide always looks the same on a second visit.

## License

MIT.
