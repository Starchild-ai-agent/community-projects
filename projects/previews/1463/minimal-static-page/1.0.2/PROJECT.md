# Venice Key Demo Page

Interactive Venice API demo page with secure backend proxy routes.

## What

Preview app with three actions: account balance lookup, model listing, and quick chat completion. Frontend stores optional user key in browser localStorage and calls backend `/api/*` routes; backend uses server-side key fallback from environment.

## Required env

Optional:
- `VENICE_API_KEY` (fallback key for backend when user does not provide one)

## How to start

Run from project root:

```
pip install flask
python src/server.py
```

Then open the preview URL served by Starchild.

## Outputs

- Web UI: `src/index.html`
- Backend API proxy: `src/server.py`

## Troubleshooting

- If requests return 400 `缺少 Venice API Key`, provide key in UI or set `VENICE_API_KEY`
- If model call fails, confirm model id exists in Venice `/models`
- Ensure frontend uses relative paths (`/api/*` under preview proxy)
