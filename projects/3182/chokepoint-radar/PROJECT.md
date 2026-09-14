# Chokepoint Radar

An editorial dark-mode dashboard visualizing the five maritime oil chokepoints
(Hormuz, Bab el-Mandeb, Malacca, Danish Straits, Bosphorus): transit flows,
exposure ratings, and an interactive scenario slider estimating illustrative
disruption premiums per barrel.

## What it does

- Five chokepoint cards with flow estimates, share-of-seaborne-oil bars and
  disruption multiplier tags
- A four-metric system strip (seaborne oil volume, chokepoint exposure share,
  reroute detour days, shock premium range)
- An interactive "Scenario" slider that recalculates an illustrative
  shock-premium figure with plain-language interpretation
- Hover/tap tooltips on each card with the underlying risk note

## Scope & honesty

All numbers are **illustrative scenario data** compiled September 2026 —
order-of-magnitude estimates, not live market data. The page is informational
only and is not financial advice.

## Stack

Single self-contained HTML file (vanilla HTML/CSS/JS, no frameworks, no
external requests). Respects `prefers-reduced-motion`. Responsive 1/2/3-column
layout.

## Required env

None. Chokepoint Radar is fully static and needs no API keys or secrets. An
empty `.env.example` is included for layout consistency.

## How to start

Open `src/index.html` directly in any browser — no build step, no server, no
network access required. To serve it over HTTP instead:

```bash
cd src && python3 -m http.server 8812
```

## Outputs / Behavior

- `index.html` renders the full dashboard: five chokepoint cards, a four-metric
  summary strip, a "How to read this" expandable section, and a footer
  disclaimer.
- Hovering or focusing a card shows a tooltip with its risk note.
- The Scenario slider (0–100%) recalculates an illustrative shock-premium
  figure and updates an interpretive note — purely local computation.

## Troubleshooting

- **Page renders but looks unstyled** — you opened a partial file; make sure
  you load the complete `src/index.html` (single self-contained file).
- **Slider does not respond** — JavaScript may be disabled in your browser;
  the page is interactive-only when JS is enabled.
- **Tooltips stay visible** — they auto-hide on scroll; if not, refresh the
  page.
- **Layout collapses to one column** — that is the intended responsive
  behavior below 720px viewport width.

## Run

Open `src/index.html` in any browser — no build step, no server required.
