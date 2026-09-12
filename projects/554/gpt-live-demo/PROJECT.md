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
- Starchild brain endpoint is hardcoded to `localhost:8000/chat/stream` inside the platform; standalone deploys need a reachable agent SSE endpoint

## How to start

```
In any Starchild agent: fork community project 554/gpt-live-demo (or `python3 -c "import sys; sys.path.insert(0,'skills/community-publish'); from exports import fork; print(fork('554/gpt-live-demo'))"`)
cd skills/gpt-live-demo/scripts
npm install
node server.mjs        # relay on :3000
# then open http://localhost:3000 in the browser and press Call
```

## Outputs / Behavior

- Dual-pane UI: chat bubbles + live event log (delegation / tool / result), per-second billing meter
- Recent voice history is re-injected into each new session (memory re-injection) and persisted to `data/voice-history.json` across restarts
- Backend tool routing: ask_starchild / check_task / cancel_task / list_tasks / memory_lookup; tasks persisted to `data/tasks.json` (done tasks kept 1h)
- GPT-Live delegates tasks to the Starchild agent via the relay; the agent's streamed progress is injected back into the live session (`session.thinking.append`) so the voice reports intermediate status
- Billing/per-second counters shown in the UI

## Troubleshooting

- **403/401 on relay** — auth path wrong: the Starchild call must go through the platform proxy with injected credentials, check `STARCHILD_AGENT_PORT` and proxy env
- **504 from agent bridge** — the agent SSE can exceed the gateway timeout; relay already switched to async polling, check `server.mjs` logs
- **No audio** — browser must be on HTTPS or localhost for microphone permission; check the OpenAI session creation response for ephemeral token errors
- **OOM in container** — keep `node --max-old-space-size` modest; the demo needs well under 1 GB
