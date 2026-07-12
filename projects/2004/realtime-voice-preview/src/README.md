# Realtime Voice Preview

This is a forkable template for the **Realtime Voice Preview** skill — a WebRTC-based real-time voice interface that connects OpenAI's Realtime API to your Starchild Agent. Speak naturally, interrupt mid-sentence, and trigger agent tools via voice.

## What's ready

| File | Purpose |
|---|---|
| `smoke.py` | Server-side WebSocket smoke test: text in → audio out → `hello.wav` |
| `server.py` | Tiny backend: mint ephemeral token + `ask_starchild` bridge |
| `index.html` | Browser WebRTC voice UI (mic + interrupt + function tools) |
| `parser.js` | Function-call argument parser (used by the browser UI) |
| `test_function_calls.js` | Node.js unit tests for the parser (59 cases) |

## Prerequisites

1. `OPENAI_REALTIME_API_KEY` set in your environment or in a project-local `.env` — a standard OpenAI API key from **platform.openai.com**.
2. Billing credit balance > 0 on that org/project.
3. Key must list realtime models (`gpt-realtime-2.1`, etc.).
4. *(Optional)* A running Starchild Agent runtime at `STARCHILD_RUNTIME_URL` (default `http://127.0.0.1:8000`) — required only for the `ask_starchild` tool bridge.

## Step 1 — smoke (no browser)

```bash
python3 src/smoke.py
# success → hello.wav + transcript on stdout
```

This connects to OpenAI's Realtime API over WebSocket, sends a single greeting prompt, writes the audio response to `hello.wav`, and prints the transcript + usage stats. No browser, no Starchild runtime needed.

## Step 2 — WebRTC voice demo

```bash
python3 src/server.py
# listen on http://0.0.0.0:8765 (port configurable via REALTIME_DEMO_PORT)
```

Then open the preview URL (or `http://127.0.0.1:8765/`), click **Connect**, allow microphone access.

Suggested probes:
- Speak freely (interrupt mid-sentence)
- Tool path: "ask Starchild about my account" → should hit `ask_starchild` → `/agent_bridge`

## Step 3 — parser tests

```bash
node src/test_function_calls.js
# 59 tests, exits non-zero on failure
```

## Architecture choice (target product)

```
Browser mic ──WebRTC──► OpenAI Realtime (VAD / turn / interrupt / speech)
                              │
                              ├─ function tools (phase 1, controllable)
                              │      └─ Starchild bridge / agent runtime
                              │
                              └─ remote MCP tools (phase 2, elegant)
                                     └─ public MCP endpoint of the agent
```

- **Phase 1 (now):** function calling bridge — full control, easy approvals, private systems stay private.
- **Phase 2:** attach `{type:"mcp", server_url, allowed_tools, require_approval}` on the session so OpenAI calls Starchild MCP directly.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/` | Serves `index.html` |
| `GET`  | `/health` | Liveness + current model/voice |
| `GET`  | `/bridge_config` | Current bridge config + runtime models |
| `POST` | `/bridge_config` | Update bridge config (agent_id, model, thread_mode, system_prompt) |
| `GET`  | `/token` | Ephemeral client_secret (legacy fallback path) |
| `POST` | `/session` | Unified WebRTC: SDP offer → answer SDP (WAF-safe via base64) |
| `POST` | `/agent_bridge` | Dispatch `ask_starchild` to the local Starchild Agent runtime |

## Security notes

- Long-lived API key **never** enters the browser — only ephemeral `client_secrets`.
- Narrow tool surface; require approval for irreversible actions.
- MCP servers do **not** receive full conversation context — only tool-call args.
- `.env` is git-ignored. Never commit your key.
- Thread-level locks + a 15s result cache prevent duplicate agent runs from concurrent Realtime events.

## Customizing for your fork

- **Runtime URL:** set `STARCHILD_RUNTIME_URL` (default `http://127.0.0.1:8000`).
- **Model:** set `REALTIME_MODEL` (default `gpt-realtime-2.1`).
- **Voice:** set `REALTIME_VOICE` (default `marin`).
- **Port:** set `REALTIME_DEMO_PORT` (default `8765`).
- **API key location:** the server checks `OPENAI_REALTIME_API_KEY` / `OPENAI_API_KEY` in this order: (1) shell environment, (2) `<project-root>/.env`, (3) `cwd/.env`.

Place your `.env` at the project root (parent of `src/`) or export the key in your shell.