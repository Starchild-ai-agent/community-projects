# Signal Lantern

## What
Signal Lantern is a local-first decision check-in board. Capture a decision, name your confidence, choose the next move, and keep a small queue of commitments you can actually review.

## Required env
None. The project uses no external services or API keys.

## How to start
Open `src/index.html` directly in a modern browser, or serve the project directory with any static file server.

## Outputs
A responsive browser interface with local persistence, filtering, completion states, deletion, and light/dark themes. Data remains in the current browser via `localStorage`.

## Troubleshooting
If entries do not persist, make sure browser storage is enabled and the page is not opened in a private browsing mode that clears storage. Clearing site data resets the board.
