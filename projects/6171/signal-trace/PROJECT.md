# Signal Trace

## What

Signal Trace is a standalone, single-page, dark-tech browser utility for
parsing, filtering, and visualizing automation event logs. It turns raw JSON
events into an observable proof of automation success with timeline views,
status summaries, and exportable reports.

## Required env

No environment variables are required. The application runs entirely in the
browser with no build step or server.

## How to start

1. Open `src/index.html` in any modern browser (Chrome, Firefox, Edge, Safari).
2. Paste one JSON object per line or a JSON array into the input panel.
3. Click **Parse** or load **Sample Data** to explore.
4. Filter by status, search by keyword, and export the report as JSON.

No dependencies, no packages, no build tools.

## Outputs

- Parsed event timeline rendered as an interactive table.
- Summary counts: total events, pass, warn, fail.
- Copy report to clipboard (JSON).
- Export report as a downloadable JSON file.

## Troubleshooting

- **Parse errors**: Ensure each line is valid JSON or the input is a single
  well-formed JSON array. The error message shows the problematic line and
  character position.
- **Empty results**: Check that parsed events contain at least a `step` field;
  events without a step are still counted but may render without a label.
- **Styling issues**: The app uses CSS custom properties; if neon colors do not
  appear, ensure your browser supports `:root` variables and CSS Grid.
- **Clipboard copy**: Browsers require user gesture (click) to copy; use the
  provided **Copy Report** button rather than programmatic access.
