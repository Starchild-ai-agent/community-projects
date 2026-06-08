# decarbon-alpha-warroom

## What
A one-page execution dashboard that:
- Detects market regime (RISK_ON / RISK_OFF / PANIC)
- Ranks pullback opportunities from your watchlist
- Generates a 9-column execution table (First Buy, Add1, Add2, Stop, Target, Upside, Action)

## Required env
None.

## How to start
From workspace root:

```bash
python3 output/projects/decarbon-alpha-warroom/src/server.py
```

Then serve it via preview using port `8765`.

## Outputs
- Web UI: one-page war room dashboard
- API endpoint: `/api/snapshot`

## Troubleshooting
- If data is unavailable, the page shows a warning row and keeps rendering.
- If preview is blank, restart preview service.
