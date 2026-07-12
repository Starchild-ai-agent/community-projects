# Starchild Live — User Guide

## What

A WebRTC realtime voice interface that connects OpenAI's Realtime API to your
Starchild Agent. OpenAI handles speech capture, VAD (voice activity detection —
when the user starts and stops speaking), interruption and turn-taking only.
Every Agent capability (reasoning, tools, memory, files, workspace) is reached
through one gateway tool: `ask_starchild`.

> **This is OpenAI Realtime, not Grok.** The model, the URL namespace
> (`wss://api.openai.com/...`) and the audio-codec conventions all belong to
> OpenAI. The Starchild side contributes routing, tools and job bookkeeping,
> but it does **not** replace the model layer.

---

## Required env

- `OPENAI_REALTIME_API_KEY` — required; collect it with Starchild's secure
  `request_env_input` flow. Never paste it into chat.
- `STARCHILD_RUNTIME_URL` — optional; defaults to `http://127.0.0.1:8000`.
- `REALTIME_MODEL`, `REALTIME_VOICE`, and `REALTIME_DEMO_PORT` — optional overrides.

## 1. Prerequisites

1. **OpenAI API key** with Realtime-model access and an active billing/credit
   balance on that org/project.
   * Get one at: `https://platform.openai.com/api-keys` (sign in, *Create new
     secret key*, copy the value once — it is shown only at creation time).
   * Enable billing on the project that owns the key; Realtime is paid per
     audio-second so a non-zero credit balance is required to hear any output.
   * The same project must have access to a Realtime model (default:
     `gpt-realtime-2.1`).
   * **Avoid unnecessary scopes.** Prefer a project-scoped key with **only**
     `api` access; do not grant `write` to other products, do not grant
     `org:read`, and never paste the key into the browser, into logs, or into a
     chat message.
   * The server reuses a single long-lived key for minting ephemeral client
     secrets (per-WebRTC-session). Rotate by replacing this key.

2. **Node.js** for the parser test suite.

3. *(Optional)* A running Starchild Agent runtime at `STARCHILD_RUNTIME_URL`
   (default `http://127.0.0.1:8000`) — required for the `ask_starchild`
   gateway. The realtime UI still runs without it, but voice calls will only
   echo back until the runtime is reachable.

---

## 2. Configure the key (never paste it in chat)

The Starchild agent must collect the key through the **secure environment prompt**
(`request_env_input`) so it never appears in chat history, terminal logs, or git
history. Never paste the key into chat and do not ask the agent to print it.

The secure prompt stores `OPENAI_REALTIME_API_KEY` in the workspace environment. The
server also supports a project-local `.env` for non-Starchild deployments, but the
Starchild setup flow always uses secure environment input. `.env` is git-ignored and
the setup script never creates or overwrites it.

---

## How to start

## 3. Install / start / test

```bash
# One-shot setup + readiness check (copies template if missing, verifies key,
# runtime, Node and both test suites):
python3 skills/realtime-voice-preview/scripts/setup.py

# Start from the generated project directory (foreground; Ctrl-C to stop):
python3 output/projects/realtime-voice-preview/src/server.py
# → listens on http://0.0.0.0:8765 by default

# Smoke (no browser needed; writes hello.wav next to the smoke output dir):
python3 output/projects/realtime-voice-preview/src/smoke.py

# Parser unit tests (Node):
node output/projects/realtime-voice-preview/src/test_function_calls.js
# Expected: PASS: 59 / FAIL: 0

# Background-jobs unit tests (Python):
python3 output/projects/realtime-voice-preview/src/test_background_jobs.py
# Expected: Ran 16 tests ... OK
```

Serve the demo with the Preview tool using **exactly**:

| Field    | Value                                          |
|----------|------------------------------------------------|
| `title`  | `OpenAI Realtime Voice Demo`                   |
| `dir`    | `output/projects/realtime-voice-preview/src`   |
| `command`| `python3 server.py`                            |
| `port`   | `8765`                                         |

Keep the `title` **constant** across restarts. The Preview ID is derived from
the title slug; renaming the title silently mints a new ID and breaks the URL
you saved. Branding changes belong in the HTML `<title>` and on-page copy
only, never in the serve `title`.

After Preview reports serving, verify health from your shell:

```bash
curl -sS http://127.0.0.1:8765/health
# → {"status":"ok", ...}
```

---

## 4. Open the demo in a separate full-screen tab

Microphone permission can be blocked or unreliable inside an embedded Preview iframe.
Always open the preview URL in its **own browser tab** (use the Preview panel's open-in-new-tab
or pop-out action) and preferably use **full-screen** while testing.

When the page first asks for microphone permission, click **Allow**. The
permission is bound to the origin (host + port), not the tab, so reloading
the page does not re-prompt — but opening from a different Preview ID (see
§3) will.

In the full-screen tab:

1. Click **Connect** to start the WebRTC session.
2. Speak naturally; you can interrupt mid-sentence.
3. Ask things like *"ask Starchild about my account"* — the Realtime model
   will emit a function call to `ask_starchild`, which forwards verbatim to
   the Starchild runtime and speaks the answer back.

---

## 5. Thread route (Temporary / Persistent / titled work threads)

Agent Settings exposes one selector, in this fixed order:

1. **Temporary — do not enter an existing thread** *(default)*. The server sets
   `is_temporary=True`. No read, no write to any work thread. Because there
   is no persisted history, the browser keeps a rolling ~12-turn transcript
   and sends a compact `context` block to the agent so elliptical follow-ups
   (e.g. *"那第二个呢"*) can still resolve.
2. **Persistent voice thread** — a dedicated voice-only context.
3. **Recent work threads**, newest first, sourced from the authenticated
   Thread Service (`/api/clawd/threads`, not runtime `/sessions`). Each
   option shows the **title** with message count/activity as secondary
   context. The thread ID is only the internal option value. Filter out
   temporary/voice/transport threads and cap the list.

The browser only ships the selected `route` when saving `/bridge_config`.
The server ignores any per-call `thread_id` sent to `/agent_bridge`.

The dropdown is rendered **title-first**: users pick *the conversation they
recognise*, not a raw ID. Picking a recent titled work thread shares and
updates that thread's context. Temporary is the default because most voice
sessions are throwaway questions, and you should not pollute a real work
thread just by talking.

---

## 6. Background jobs (how voice never hangs)

`ask_starchild` accepts `execution_mode: auto | wait | background`:

* `wait` — run within a short safe budget; if unfinished, auto-promote to
  HTTP 202 with a resumable `run_id` **before** the Preview gateway returns
  an HTML timeout page.
* `background` — return HTTP 202 with an accepted `run_id` immediately.
* `auto` — short ordinary questions use the bounded wait path; explicit
  *background/continue* cues or long task-like prompts use background.

For an HTTP 202 the client must:

1. Send exactly one `function_call_output` acknowledging the accepted
   `run_id` (no more — the terminal result is a new conversation message,
   never a second output for the original `call_id`).
2. Persist pending job metadata + a bounded delivered-ID set in
   `localStorage`.
3. Poll `GET /agent_jobs?run_id=...` ~every 2 seconds.
4. Offer cancel via `POST /agent_jobs/cancel`.
5. Recover active jobs after reload/reconnect with `GET /agent_jobs`.
6. If disconnected, keep a terminal result as pending.
7. When the data channel is open, inject the verified terminal result once,
   mark it delivered, then ask Realtime to speak it via the existing
   response/continuation guard.

Cancellation is **cooperative**: `cancel_requested` is active, not terminal;
the server only reports `cancelled` after the worker observes the flag. One
active job per effective thread; a recent identical job reuses its `run_id`.

---

## Outputs

- A browser-based realtime voice session connected to the user's own Starchild Agent.
- Temporary, persistent voice, and titled work-thread routing modes.
- Resumable background-job status and verified final result delivery in the UI.
- Optional `hello.wav` generated only when the user explicitly runs the smoke test.

## 7. Environment variables

| Var                      | Required | Default                          | Notes                                       |
|--------------------------|----------|----------------------------------|---------------------------------------------|
| `OPENAI_REALTIME_API_KEY`| **yes**  | —                                | Long-lived OpenAI key; server-side only.    |
| `STARCHILD_RUNTIME_URL`  | no       | `http://127.0.0.1:8000`          | Agent runtime base URL.                     |
| `REALTIME_MODEL`         | no       | `gpt-realtime-2.1`               | Realtime model id.                          |
| `REALTIME_VOICE`         | no       | `marin`                          | Voice preset.                               |
| `REALTIME_DEMO_PORT`     | no       | `8765`                           | HTTP port for the demo server.              |

---

## 8. Endpoints

| Method   | Path                              | Purpose                                                       |
|----------|-----------------------------------|---------------------------------------------------------------|
| `GET`    | `/`                               | Serves `index.html`.                                          |
| `GET`    | `/health`                         | Liveness + current model/voice + bridge config.               |
| `GET`    | `/token`                          | Ephemeral client secret (legacy fallback).                    |
| `POST`   | `/session`                        | Unified WebRTC: SDP offer → SDP answer (base64-wrapped).      |
| `GET`    | `/bridge_config`                  | Current bridge config + runtime model list.                   |
| `POST`   | `/bridge_config`                  | Save the selected `route` (Temporary / Persistent / titled).  |
| `GET`    | `/bridge_threads?agent_id=...`    | Titled work-thread catalog for the dropdown.                 |
| `POST`   | `/agent_bridge`                   | Dispatch `ask_starchild` to the Starchild runtime.            |
| `GET`    | `/agent_jobs`                     | List active/pending jobs (recovery after reload).            |
| `GET`    | `/agent_jobs?run_id=...`          | Poll one job.                                                 |
| `POST`   | `/agent_jobs/cancel`              | Request cooperative cancellation.                             |

---

## Troubleshooting

| Symptom                                                    | Check                                                                                          |
|------------------------------------------------------------|------------------------------------------------------------------------------------------------|
| `OPENAI_REALTIME_API_KEY missing`                          | Ask the agent to open the secure key-input flow again; never paste the key into chat. |
| `setup.py` reports key present but server still 401s       | Key revoked, or project lacks Realtime model access, or the org has zero credit.                |
| No sound / connection fails                                 | OpenAI billing/credit, Realtime model access, browser mic permission, full-screen tab.         |
| `ask_starchild` returns connection refused                 | `STARCHILD_RUNTIME_URL` not set or wrong; check `curl http://127.0.0.1:8000/health`.           |
| `Unexpected token '<'` after ~30 s                          | Preview gateway returned HTML while a synchronous request was still running — the server must auto-promote `wait` to a `run_id` and the client must validate text before JSON parsing. |
| Voice cuts off / query interrupted                          | Duplicate tabs/calls; serialization and the short completed-result cache must remain enabled.   |
| Work-thread option rejected                                 | Refresh `/bridge_threads` and pick a recent titled option, or fall back to Temporary.          |
| Job result not spoken after reload                          | Confirm the run is still pending locally, the data channel is open, and the delivered-ID set does not already contain it. |
| Cancel stuck at `cancel_requested`                          | Cancellation is cooperative — wait for the worker to confirm a terminal state.                  |
| `gyp ERR! ... node-gyp`                                    | Node too old for `index.html`-served bundled deps; use Node 18+ LTS.                            |

---

## 10. Security checklist (do these before sharing)

* The long-lived key was collected through secure environment input and never appears in chat or logs.
* The Preview is opened in its own browser tab, preferably full-screen, rather than the embedded iframe.
* Rotate the OpenAI key by re-issuing it under the same project; never paste
  the new key in chat.
* Review `/bridge_config` permissions periodically: per-call `thread_id`
  overrides are intentionally ignored; only the saved `route` is honoured.
