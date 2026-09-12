# GPT-Live Voice Receptionist Demo

## What

A complete GPT-Live voice demo packaged as an installable Starchild skill:

- `scripts/index.html` — browser WebRTC client: call controls, event log, per-second billing display
- `scripts/server.mjs` — Node/Express relay: creates OpenAI WebRTC sessions and forwards client-delegation tasks to the Starchild agent
- `references/deploy.md` — local dev and production deployment steps
- `SKILL.md` + `README.md` — skill metadata and one-line install instructions

Architecture: browser (WebRTC audio + oai-events DataChannel) → OpenAI GPT-Live → relay `/api/agent` → Starchild agent (SSE) → result spoken back by GPT-Live.

## Required env

- `OPENAI_API_KEY` — OpenAI key with GPT-Live access (relay uses it to mint WebRTC session tokens)
- `STARCHILD_AGENT_PORT` — port of the local Starchild agent API (default 8000)
- Starchild agent key is injected by the platform proxy; on a bare server set `SC_AGENT_KEY`

## How to start

```
npx skills@latest add jotaro-ora/gpt-live-demo-skill --agent openclaw
cd skills/gpt-live-demo/scripts
npm install
node server.mjs        # relay on :3000
# then open http://localhost:3000 in the browser and press Call
```

## Outputs / Behavior

- Browser establishes a WebRTC call with GPT-Live; the transcript and delegation events stream into the on-page log
- GPT-Live delegates tasks to the Starchild agent via the relay; the agent's streamed progress is injected back into the live session (`session.thinking.append`) so the voice reports intermediate status
- Billing/per-second counters shown in the UI

## Troubleshooting

- **403/401 on relay** — auth path wrong: the Starchild call must go through the platform proxy with injected credentials, check `STARCHILD_AGENT_PORT` and proxy env
- **504 from agent bridge** — the agent SSE can exceed the gateway timeout; relay already switched to async polling, check `server.mjs` logs
- **No audio** — browser must be on HTTPS or localhost for microphone permission; check the OpenAI session creation response for ephemeral token errors
- **OOM in container** — keep `node --max-old-space-size` modest; the demo needs well under 1 GB
