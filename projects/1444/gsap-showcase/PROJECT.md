# GSAP Skills Showcase

A single-page interactive demo of all **8 official GSAP skills**, showing what each one can do in the browser. Use it to learn the skill suite, or fork it as a starting template for production animations.

## What

12 self-contained sections, each mapped to one or more GSAP skill, with auto-play on scroll and clickable controls.

| Section | Demo | Skill(s) |
|---------|------|----------|
| Hero | Title fade-up + chip stagger | gsap-core |
| ① Eases | 12 easing curves side-by-side | gsap-core |
| ② Stagger | 100-cell grid with 4 stagger modes (start/center/edges/random) | gsap-core |
| ③ Timeline | 4-step timeline with play/pause/reverse + draggable progress | gsap-timeline |
| ④ Scrub | SVG circle stroke + counter driven by scroll | gsap-scrolltrigger |
| ⑤ Pin + Parallax | 3-layer depth scroll with pinned section | gsap-scrolltrigger |
| ⑥ Flip | Grid ↔ List ↔ Stack layout transitions | gsap-plugins (Flip) |
| ⑦ Draggable | Bounded card drag with press feedback | gsap-plugins (Draggable) |
| ⑧ MotionPath | Object follows SVG path with auto-rotate | gsap-plugins (MotionPath) |
| ⑨ SplitText | Animate by chars / words / lines | gsap-plugins (SplitText) |
| ⑩ Utils | Live clamp / mapRange / snap / normalize demo | gsap-utils |
| ⑪ Performance | `left` vs `x` side-by-side (open DevTools to see FPS diff) | gsap-performance |
| ⑫ Frameworks | React / Vue / Svelte integration snippets | gsap-react, gsap-frameworks |
| 📦 Install | Where to get the skills + how to fork | — |

## Required env

None. All GSAP plugins loaded from jsDelivr CDN — no API keys.

## How to start

Static site, any HTTP server works:

```bash
cd src
python3 -m http.server 8910 --bind 127.0.0.1
```

Open `http://localhost:8910/` (or the Starchild preview URL if running in-container).

Inside Starchild:

```python
preview(action='serve',
        title='GSAP Skills Showcase',
        dir='output/projects/gsap-showcase/src',
        command='python3 -m http.server 8910 --bind 127.0.0.1',
        port=8910)
```

## Where to get the GSAP skills

All 8 skills come from `greensock/gsap-skills` on GitHub. In Starchild, just ask your agent:

> "install GSAP skills"

The agent will use `search_skills` to install them from the community registry. Once installed, the agent will automatically read each skill's `SKILL.md` when you ask for GSAP work — no manual loading needed.

Individual install (if you only need part of the suite):

| Skill | When to install |
|-------|-----------------|
| `gsap-core` | Always — every other skill builds on it |
| `gsap-timeline` | Multi-step animation sequencing |
| `gsap-scrolltrigger` | Scroll-driven animation, pin, scrub, parallax |
| `gsap-plugins` | Flip, Draggable, MotionPath, SplitText, ScrollSmoother, etc. |
| `gsap-utils` | Math helpers (clamp, mapRange, random, snap) |
| `gsap-react` | React-specific `useGSAP` hook + cleanup |
| `gsap-frameworks` | Vue 3 / Svelte cleanup patterns |
| `gsap-performance` | Performance audits & best practices |

## Outputs

Pure browser-side. No files written, no API calls, no telemetry.

## Troubleshooting

- **Nothing animates** — open browser DevTools console; the bottom-left "diag" indicator in the sidebar shows which section failed to init.
- **Sidebar nav doesn't highlight** — ScrollTrigger failed to load from CDN; check network tab.
- **SplitText doesn't work** — automatic fallback to manual character split kicks in (visually identical).
- **Animations stutter on mobile** — section ⑤ (Pin + Parallax) is GPU-heavy; reduce `end` distance in `main.js` if needed.

## License

Showcase code: MIT. GSAP itself: also free (including all formerly Club-only plugins) since Webflow's 2024 acquisition.
