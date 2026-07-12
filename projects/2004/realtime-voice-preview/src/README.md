# Realtime Voice Preview — `src/` README

This is the **OpenAI Realtime voice layer** for Starchild Live. The Realtime
model only does speech, voice-activity detection (VAD), interruption, and
turn-taking. Anything that requires understanding your data — projects, files,
memories, balances, tools, actions — is routed to your Starchild Agent via
the single gateway tool `ask_starchild`.

> **Provider:** this is **OpenAI** (Realtime API, WebRTC), **not Grok**. The
> URL namespace (`wss://api.openai.com/v1/realtime`) and the audio codec
> conventions belong to OpenAI. Starchild contributes routing and tooling
> only.

---

## What's in this folder

| File                       | Purpose                                                                     |
|----------------------------|-----------------------------------------------------------------------------|
| `server.py`                | Tiny backend. Mints ephemeral client secrets and bridges `ask_starchild`.   |
| `index.html`               | Browser WebRTC voice UI (mic, interrupt, function tools, jobs panel).       |
| `parser.js`                | Pure function-call argument parser shared by the browser and Node tests.    |
| `test_function_calls.js`   | Node unit tests for the parser (**59** cases).                              |
| `test_background_jobs.py`  | Python unit tests for `/agent_jobs` lifecycle and serialization (**16**).   |
| `smoke.py`                 | CLI WebSocket smoke: text in → audio out → `hello.wav` (no browser needed).  |
| `README.md`                | This file.                                                                  |

---

## 1. Prerequisites (one-time)

1. **OpenAI API key** with Realtime-model access and an active billing/credit
   balance on that project.
   * Issue: `https://platform.openai.com/api-keys` → *Create new secret key*.
   * Top up the same project at *Billing*; Realtime is paid per audio-second,
     so a non-zero credit balance is required to hear any output.
   * The same project must have access to a Realtime model (default:
     `gpt-realtime-2.1`).
   * **Limit the scope.** Prefer a project-scoped key with only `api` access;
     do not grant `org:read` or write access to other products. Never paste
     the key into chat, logs, or browser code.

2. **Node.js ≥ 18** (for the parser test suite).

3. *(Optional)* A reachable Starchild Agent runtime at `STARCHILD_RUNTIME_URL`
   (default `http://127.0.0.1:8000`). Without it, `ask_starchild` will not be
   able to reach your agent; the realtime model will still speak, but every
   tool call will error.

---

## 2. Configure the key (securely)

Use the skill's `request_env_input` mechanism. It stores
`OPENAI_REALTIME_API_KEY` securely in the workspace environment without putting the
value in chat history. Never paste the key into chat, source files, commands, or logs.

The server keeps the long-lived key server-side. The browser receives only ephemeral
per-session `client_secret` values.

---

## 3. Install / start / test

```bash
# From the project root (parent of src/):
python3 skills/realtime-voice-preview/scripts/setup.py
python3 output/projects/realtime-voice-preview/src/server.py
curl -sS http://127.0.0.1:8765/health

node output/projects/realtime-voice-preview/src/test_function_calls.js
python3 output/projects/realtime-voice-preview/src/test_background_jobs.py
python3 output/projects/realtime-voice-preview/src/smoke.py
```

Serve the demo with the Preview tool:

| Field     | Value                                          |
|-----------|------------------------------------------------|
| `title`   | `OpenAI Realtime Voice Demo`                   |
| `dir`     | `output/projects/realtime-voice-preview/src`   |
| `command` | `python3 server.py`                            |
| `port`    | `8765`                                         |

Keep `title` constant across restarts — the Preview ID is derived from the
title slug; renaming it silently mints a new ID and breaks your saved URL.
Branding changes belong in the HTML `<title>` and on-page copy only.

---

## 4. Open in a separate full-screen browser tab

Microphone permission can be blocked or unreliable inside an embedded Preview iframe.
Always open the Preview URL in its **own browser tab** (use the Preview panel's
open-in-new-tab or pop-out action) and preferably test **full-screen**.

The first time the page loads, the browser prompts for microphone access.
Click **Allow**. The permission is bound to the origin (host + port), not the
tab, so reloading does not re-prompt — but a fresh Preview ID (after a rename
of the serve `title`) counts as a new origin.

Once connected:

* Speak naturally — interrupt whenever you want.
* Trigger tools: *"ask Starchild about my account"* makes Realtime emit
  `ask_starchild`, which is forwarded to the Starchild runtime and spoken
  back. Pick the thread route in **Agent Settings**:

  1. **Temporary — do not enter an existing thread** *(default)*. No read or
     write to any work thread. Rolling transcript is kept in the browser for
     follow-ups.
  2. **Persistent voice thread** — dedicated voice-only context.
  3. **Recent work threads** (titled, newest first) — picks and continues an
     existing thread by title; the underlying ID is hidden from the user.

---

## 5. Customisation knobs

| Env var                   | Default                   | Purpose                                  |
|---------------------------|---------------------------|------------------------------------------|
| `STARCHILD_RUNTIME_URL`   | `http://127.0.0.1:8000`   | Starchild Agent runtime base.            |
| `REALTIME_MODEL`          | `gpt-realtime-2.1`        | Realtime model id.                       |
| `REALTIME_VOICE`          | `marin`                   | Voice preset.                            |
| `REALTIME_DEMO_PORT`      | `8765`                    | HTTP port for the demo server.           |
| `OPENAI_REALTIME_API_KEY` | *none*                    | Long-lived OpenAI key (server-side).     |

Key lookup order: (1) shell environment, (2) `<project-root>/.env`,
(3) `cwd/.env`.

---

## 6. Endpoints exposed by `server.py`

| Method         | Path                              | Purpose                                                       |
|----------------|-----------------------------------|---------------------------------------------------------------|
| `GET`          | `/`                               | Serves `index.html`.                                          |
| `GET`          | `/health`                         | Liveness + current model/voice + bridge config.               |
| `GET`          | `/token`                          | Ephemeral client secret (legacy fallback).                    |
| `POST`         | `/session`                        | Unified WebRTC: SDP offer → SDP answer (base64-wrapped).      |
| `GET`          | `/bridge_config`                  | Current bridge config + runtime model list.                   |
| `POST`         | `/bridge_config`                  | Save the selected `route` (Temporary / Persistent / titled).  |
| `GET`          | `/bridge_threads?agent_id=...`    | Titled work-thread catalog.                                   |
| `POST`         | `/agent_bridge`                   | Dispatch `ask_starchild` to the Starchild runtime.            |
| `GET`          | `/agent_jobs`                     | Active/pending jobs (recovery after reload).                 |
| `GET`          | `/agent_jobs?run_id=...`          | Poll a single job.                                            |
| `POST`         | `/agent_jobs/cancel`              | Cooperative cancellation.                                     |

---

## 7. Temporary vs Persistent vs titled thread (titled-thread mode)

| Mode               | Reads history | Writes           | `is_temporary` | Context block sent |
|--------------------|---------------|------------------|----------------|---------------------|
| Temporary (default)| no            | no               | `true`         | rolling ~6 turns    |
| Persistent         | yes (voice)   | yes (voice only) | `false`        | none                |
| Selected titled    | yes (that thread) | yes (that thread) | `false`    | none                |

Why **Temporary** is the default: most voice sessions are throwaway
questions, so opting into a real work thread should be deliberate. Why
**titled** rather than ID-only: a raw thread id is meaningless to a user;
the dropdown shows titles with message-count/activity as secondary text.

---

## 8. Background-job lifecycle

* `ask_starchild(question, execution_mode?)` with `auto|wait|background`.
* `wait` is bounded by a safe timeout; if it has not finished, the server
  auto-promotes to HTTP 202 with a resumable `run_id`.
* `background` returns 202 immediately.
* Client persists pending jobs + a bounded delivered-ID set in
  `localStorage`, polls `/agent_jobs?run_id=...` every ~2 s, and recovers
  active jobs after reload.
* Verified terminal results are injected into Realtime **once** as a new
  conversation message (not a second `function_call_output`).
* Cancellation is cooperative: `cancel_requested` is not terminal until the
  worker reports it.

---

## 9. Architecture (target product)

```
Browser mic ──WebRTC──► OpenAI Realtime  (VAD / turn / interrupt / speech)
                              │
                              ├─ function tools (now)
                              │      └─ ask_starchild → Starchild Agent bridge
                              │
                              └─ remote MCP tools (later)
                                     └─ public MCP endpoint of the agent
```

* **Phase 1 (current):** function-calling bridge — full control, easy
  approvals, private systems stay private.
* **Phase 2 (later):** attach `{type:"mcp", server_url, allowed_tools,
  require_approval}` on the session so OpenAI calls Starchild MCP directly.

---

## 10. Security checklist

* `.env` exists, is git-ignored, holds **only** the long-lived OpenAI key.
* The Preview tab is opened in its **own** browser window — never inside the
  embedded Preview iframe, which cannot capture the microphone.
* Rotate the OpenAI key by re-issuing under the same project; never paste
  the new value in chat.
* Per-call `thread_id` overrides are deliberately ignored at `/agent_bridge`;
  only the saved `route` is honoured.
* SDP answers are base64-wrapped inside JSON to survive the Preview proxy.

---

## 11. Troubleshooting (quick map)

| Symptom                                                  | Check                                                                          |
|----------------------------------------------------------|--------------------------------------------------------------------------------|
| `OPENAI_REALTIME_API_KEY missing`                         | Run `scripts/setup.py`; if still missing, your `.env` is unreadable.          |
| 401 from OpenAI                                          | Project lacks Realtime access, or zero credit balance.                        |
| Voice quiet / no sound                                   | Browser mic permission; full-screen tab (not Preview iframe).                 |
| `ask_starchild` returns connection refused                | `STARCHILD_RUNTIME_URL`; `curl http://127.0.0.1:8000/health`.                 |
| `Unexpected token '<'` after ~30 s                        | Server must auto-promote `wait` to `run_id`; client must validate text first. |
| Voice cuts off / query interrupted                        | Check thread serialization and the completed-result cache.                      |
| Job result not spoken after reload                        | Confirm run is still pending, data channel open, delivered-ID set excludes it. |
| Cancel stuck at `cancel_requested`                        | Cooperative cancellation; wait for the worker to confirm.                      |
