# Typewriter Font Morph

## What it is
A single-page typewriter animation. The first letter "A" rapidly cycles through 10 different fonts (Times, Impact, Comic Sans, Courier, Georgia, Arial Black, Papyrus, Verdana, Brush Script, Helvetica) over 300ms, with random case switching. It then settles on Helvetica and the remaining letters type out crisply with a subtle scale-pop. After a hold, it erases and loops.

A live control panel (top-right) lets you tune:
- How many fonts participate in the morph (2–10)
- Font-swap frequency (10–200ms)
- Typing speed (30–200ms)

## Required env
None. Pure static HTML/CSS/JS — no backend, no API keys.

## How to start
This is a `service` type project. Serve the `src/` directory with any static file server:

```bash
cd src && python3 -m http.server 8080
```

Or in Starchild: `preview(action='serve', dir='src', title='Typewriter Font Morph')`.

## Outputs
- A running web page with the looping animation
- Public URL (if published via `publish_preview`)
- Forkable source on community GitHub (if published via `open_source`)

## Troubleshooting
- **Animation looks jittery**: the morphing letter is intentionally chaotic during the first 300ms — that's the effect. After that it should be stable.
- **Rest of string shifts when A changes font**: the morphing A is held in a fixed `0.82em` width box so font swaps don't reflow the rest of the text.
- **Fonts look the same**: the 10 fonts rely on system-installed fonts. On Linux servers without Microsoft fonts, Impact/Comic Sans/Papyrus/Brush Script may fall back to defaults. For full fidelity, run on macOS or Windows, or install the Microsoft core fonts.
