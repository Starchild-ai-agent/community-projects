# Starchild Live — Design Analysis

_Realtime voice interface (OpenAI Realtime API) wired to a Starchild Agent through a
single gateway tool, `ask_starchild`. This document explains the three design questions
that shaped the architecture: the BYOK requirement, temporary vs. thread modes, and the
tool/MCP interaction model._

---

## 1. BYOK requirement (OpenAI Realtime key)

**What is required:** an `OPENAI_REALTIME_API_KEY` with Realtime-model access and active
billing. It is collected via secure input (`request_env_input`), stored server-side, and
**never** sent to the browser.

**Why BYOK, and why server-side only:**

- The Realtime API bills per audio-second, which is materially more expensive than text
  chat. Metering must sit on the account that owns the key — so the user brings their own.
- A long-lived key must never touch the client. The browser instead receives an
  **ephemeral client secret** minted server-side (`POST /session` → `GET /token`), which
  the WebRTC session uses directly. The long-lived key stays in the container env.
- This keeps the trust boundary clean: OpenAI handles only speech capture, VAD,
  interruption, and turn-taking. It never sees Starchild data, tools, or credentials.

**Consequence for the design:** OpenAI Realtime is intentionally "dumb about the user."
All knowledge (recent work, files, memory, balances, actions) is fetched through
`ask_starchild`, which runs on the Starchild runtime with the user's real session — see §3.

---

## 2. Temporary vs. thread modes

Agent Settings exposes **one** route selector. Ordering is fixed:

1. **Temporary** — _do not enter an existing thread_ (**default**).
2. **Persistent** — a dedicated voice-only context.
3. **Existing work thread** — recent normal threads, newest first, shown by **title**
   (message count/activity as secondary text). The thread ID is internal routing only and
   is never surfaced to the user, because a raw ID is meaningless to them.

| | Temporary | Persistent | Selected work thread |
|---|---|---|---|
| Reads existing history | No | Yes (voice context) | Yes (that thread) |
| Writes to a work thread | No | Voice context only | Yes |
| Internal mode | `isolated` | `persistent` | `selected` |
| `is_temporary` | `true` | `false` | `false` |

**Why temporary is the default:** most voice sessions are quick, throwaway questions. A
user should not risk polluting a real work thread just by talking. Opting into a work
thread is an explicit, deliberate choice.

**The follow-up problem, and the fix (rolling context):**
Temporary mode has no persisted history, so an elliptical follow-up like _"可以去做了吗"_
("can you go do it now?") has no server-side referent. To solve this **without** binding
to a thread, the browser keeps a rolling transcript (last ~12 turns) and sends it as an
optional `context` array with each call. The server injects it — **only** when
`is_temporary` is true — as a compact `[Recent voice conversation]` block (capped to the
last 6 turns / 1200 chars), placed ahead of the verbatim spoken request. Selected and
persistent threads already carry real history, so context injection is deliberately
skipped there to avoid duplication.

**Auditability:** every relayed message is prefixed with a stable
`[Starchild Live Voice Agent]` source marker and the spoken request is labeled, so when a
work thread is selected, its history clearly shows which turns came from voice.

---

## 3. Tool / MCP interaction design

**One gateway, not many tools.** The Realtime model is given exactly one capability tool:
`ask_starchild(question, execution_mode?)`. It is not handed the Agent's full toolset.
This is deliberate — the Agent already owns tools, memory, files, and MCP connections;
duplicating them into the Realtime layer would fork auth, break metering, and let the
voice model hallucinate Agent state. Instead, `ask_starchild` forwards the request to the
Starchild runtime (`POST /chat`), where the real Agent decides which tools/MCP servers to
invoke and returns a verified answer.

**Verbatim relay.** `question` must carry the user's transcribed words **exactly** — no
paraphrase, summary, translation, expansion, or inferred intent. Realtime owns speech and
turn-taking; understanding belongs to the Agent. If a request is genuinely ambiguous, the
model asks the user out loud to clarify rather than filling in a guess. This is enforced
in both the system instructions and the tool description so semantic drift never reaches
the Agent.

**Execution modes** (bounded by the Preview gateway timeout):

| Mode | Behavior |
|---|---|
| `wait` | Runs within a short safe budget; if unfinished, auto-promotes to HTTP 202 with a resumable `run_id` **before** the gateway would return an HTML timeout page |
| `background` | Immediately returns HTTP 202 with an accepted `run_id` |
| `auto` | Short ordinary questions use bounded wait; explicit "continue/background" or long task-like prompts use background |

**Background-job lifecycle** (the reason voice never hangs):
- Client persists pending job metadata + a bounded delivered-ID set in `localStorage`.
- Polls `GET /agent_jobs?run_id=...` ~every 2s; can cancel via `POST /agent_jobs/cancel`.
- Recovers active jobs after reload/reconnect via `GET /agent_jobs`.
- On completion, the verified result is injected **once** as a new conversation message —
  never as a second `function_call_output` for the original `call_id`.
- Cancellation is cooperative: `cancel_requested` is active, not terminal; `cancelled` is
  reported only after the worker observes the flag.
- One active job per effective thread; a recent identical job reuses its `run_id`.

**Robustness rules learned in production:**
- Bridge responses are parsed as text before JSON, so an upstream HTML error surfaces as a
  useful diagnostic instead of `Unexpected token '<'`.
- SDP is base64-wrapped inside JSON to survive the Preview proxy/WAF.
- Runtime calls are serialized per effective thread, with a short completed-result cache to
  absorb duplicate tabs/calls.

---

## Verification

```bash
python3 -m py_compile src/server.py
node src/test_function_calls.js          # 59 pass
python3 src/test_background_jobs.py      # 16 pass
```

Also confirm Preview health (HTTP 200) and the live HTML title after each restart. Keep
the Preview serve `title` constant so the URL/ID never drifts (branding changes go in the
HTML `<title>` only).
