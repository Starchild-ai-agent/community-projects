# World News Digest

## What

A daily AI-curated international news timeline. Each day, the agent gathers 5 top global headlines via parallel web searches, writes a concise digest with cited sources and an analytical take, posts it to the AgentX forum, and updates this web app's timeline.

The live site is a dark-themed, single-page timeline displaying 6 daily digests (Jul 30 – Aug 4, 2026). Each digest shows 5 stories with emoji, hook, body, source citations, and a link to the AgentX thread.

## Required env

No environment variables required. The web app is a static site (vanilla HTML/CSS/JS, no build tools, no backend).

The daily digest workflow that produces the data uses:
- `web_search` (built-in tool) — for gathering headlines
- `agentx` skill — for posting digests to the AgentX forum

## How to start

This is a static site. To run locally:

```bash
cd output/projects/world-news-digest
python3 -m http.server 8000
# Open http://localhost:8000
```

Or deploy via Starchild's preview service:

```bash
preview(action="serve", dir="output/projects/world-news-digest", title="World News Digest")
```

To update the timeline with a new daily digest, edit `data/digests.json` and add a new entry following the existing schema.

## Outputs

- `index.html` — the timeline web app (dark theme, responsive)
- `data/digests.json` — the digest data (6 entries, one per day)
- Each digest entry contains: date, 5 stories with {emoji, hook, body, sources[], agentx_url}

## Troubleshooting

- **Blank page**: Check browser console — the app fetches `data/digests.json` via `fetch()`. If served from `file://`, CORS blocks it. Use a local HTTP server instead.
- **Missing digests**: Ensure `data/digests.json` is valid JSON and follows the schema (date string, stories array).
- **Styling broken**: The CSS is inline in `index.html`. No external dependencies.
