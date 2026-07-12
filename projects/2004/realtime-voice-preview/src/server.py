#!/usr/bin/env python3
"""Local Realtime WebRTC demo for Starchild.

Two connection modes (browser prefers unified /session):
1) Unified: browser POSTs SDP to /session; server mints call with long-lived key
2) Ephemeral: browser GETs /token and POSTs SDP to OpenAI itself (fallback)

Also:
- /agent_bridge: dispatches ask_starchild to the local Starchild Agent runtime
"""

from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"
HOST = "0.0.0.0"
PORT = int(os.environ.get("REALTIME_DEMO_PORT", "8765"))
MODEL = os.environ.get("REALTIME_MODEL", "gpt-realtime-2.1")
VOICE = os.environ.get("REALTIME_VOICE", "marin")

# In-memory Agent bridge config (per-process, mutable via /bridge_config).
# Defaults are intentionally safe — no secrets, no model hardcoding.
BRIDGE_CONFIG: dict = {
    "agent_id": "main",
    "model": None,
    "thread_mode": "isolated",  # 'isolated' | 'persistent' | 'selected'
    "thread_id": None,          # validated nonempty safe id; used when mode == 'selected'
    "system_prompt": "",
}

# Cache of allowed thread ids (per agent_id) — populated by /bridge_threads. Used
# to validate thread_id set via /bridge_config. The cache TTL is short so a
# recatalogued agent keeps valid selections usable even if the periodic refresh
# misses one. We also accept thread ids currently saved in BRIDGE_CONFIG so the
# user's selection survives across refreshes until a save or a manual change.
BRIDGE_THREAD_ALLOW: dict[str, set[str]] = {}
BRIDGE_CONFIG_LOCK = threading.Lock()
LOCAL_RUNTIME_BASE = os.environ.get("STARCHILD_RUNTIME_URL", "http://127.0.0.1:8000").rstrip("/")
THREAD_SERVICE_BASE = os.environ.get("AI_AGENT_API_URL", "http://127.0.0.1:8001").rstrip("/")

# The runtime allows one active run per session key. Realtime may emit duplicate
# completion events (and multiple browser tabs may share a voice thread), so
# serialize bridge calls per effective thread. Identical requests are reused for
# a short window after the first caller completes.
BRIDGE_COORD_LOCK = threading.Lock()
BRIDGE_THREAD_LOCKS: dict[str, threading.Lock] = {}
BRIDGE_RESULT_CACHE: dict[tuple[str, str], tuple[float, dict]] = {}
BRIDGE_CACHE_TTL_SECONDS = 15.0
# Preview requests can be cut off by the outer gateway at about 30 seconds.
# A wait call therefore gets a shorter synchronous budget; unfinished work is
# returned as a resumable run_id instead of letting the gateway emit an HTML
# timeout page that the browser cannot parse as JSON.
SYNC_WAIT_BUDGET_SECONDS = float(os.environ.get("VOICE_SYNC_WAIT_BUDGET_SECONDS", "20"))

# ----- Background job registry -----
# The bridge supports an `execution_mode` of `auto|wait|background` from the
# Realtime tool call. `wait` keeps the existing synchronous 150 s HTTP path.
# `background` (and `auto` when it picks background) starts a background worker
# that runs the same serialized bridge path and stores a sanitized, terminal
# result/error. There is no percentage progress — status only. The browser
# polls `/agent_jobs?run_id=...` and injects the verified completion into the
# Realtime conversation exactly once per browser (via a delivered-run-id set
# the server never sees).
JOB_REGISTRY_LOCK = threading.Lock()
JOB_REGISTRY: dict[str, dict] = {}        # run_id -> sanitized job state
JOB_RECENT_LIMIT = 100                    # hard cap on retained jobs (no growth)
JOB_RECENT_TTL_SECONDS = 30 * 60          # 30 min — long enough for reconnect
JOB_DEDUPE_WINDOW_SECONDS = 15.0          # duplicate recent question dedupe
# Per-effective-thread "active job" gate: only one running/queued job per
# thread at a time. Re-using BRIDGE_THREAD_LOCKS for serialization is fine
# because it is already per-thread; we only add a job-id pointer here.
JOB_ACTIVE_PER_THREAD: dict[str, str] = {}
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
ACTIVE_STATUSES = {"queued", "running", "cancel_requested"}
# Explicit background phrases — kept small and deterministic so we don't
# surprise the user with auto-backgrounding of normal short queries.
_BG_HINT_PATTERNS = (
    re.compile(r"\bbackground\b", re.IGNORECASE),
    re.compile(r"\bcontinue\b\s+(?:working|in\s+the\s+background)?", re.IGNORECASE),
    re.compile(r"继续(干|做|处理|运行|工作)", re.IGNORECASE),
    re.compile(r"(后台|异步)(跑|执行|运行|处理|干)?", re.IGNORECASE),
    re.compile(r"不用等我", re.IGNORECASE),
    re.compile(r"don['’]?t\s+wait(\s+for\s+me)?", re.IGNORECASE),
)
# Crude length threshold to catch "long task-like input" without using network.
_BG_LENGTH_THRESHOLD = 480


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _make_run_id() -> str:
    # Cryptographically random UUID4 — collision-safe and short enough for UI.
    return "run_" + uuid.uuid4().hex


def _sanitize_job(job: dict) -> dict:
    """Return a wire-safe snapshot of a background job.

    The full internal record may include the raw prompt, internal flags, or
    timing telemetry. The wire response is intentionally small and only ever
    exposes what the browser legitimately needs to render and poll.
    """
    out = {
        "run_id": job.get("run_id"),
        "status": job.get("status"),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "thread_mode": job.get("thread_mode"),
        "thread_id": job.get("thread_id"),
        "is_temporary": bool(job.get("is_temporary")),
        "agent_id": job.get("agent_id"),
    }
    if job.get("status") == "completed":
        out["result"] = job.get("result")
        out["model"] = job.get("model")
    elif job.get("status") == "failed":
        out["error"] = job.get("error")
    elif job.get("status") == "cancelled":
        out["error"] = job.get("error") or "cancelled"
    # Never expose prompts, secrets, raw session IDs, or per-call routing keys.
    return out


def _job_cleanup_locked(now: float) -> None:
    """Evict stale terminal jobs past TTL or over the recent cap. Caller holds
    JOB_REGISTRY_LOCK."""
    # TTL eviction first (only for terminal jobs).
    stale = []
    for rid, j in JOB_REGISTRY.items():
        st = j.get("status")
        if st not in TERMINAL_STATUSES:
            continue
        completed = j.get("completed_at_epoch") or j.get("created_at_epoch") or now
        if now - completed > JOB_RECENT_TTL_SECONDS:
            stale.append(rid)
    for rid in stale:
        JOB_REGISTRY.pop(rid, None)
        # If it was the active job for a thread, drop the pointer.
        for tk, ar in list(JOB_ACTIVE_PER_THREAD.items()):
            if ar == rid:
                JOB_ACTIVE_PER_THREAD.pop(tk, None)
    # Cap retained recent jobs.
    if len(JOB_REGISTRY) > JOB_RECENT_LIMIT:
        terminal_jobs = [
            (rid, j) for rid, j in JOB_REGISTRY.items()
            if j.get("status") in TERMINAL_STATUSES
        ]
        terminal_jobs.sort(key=lambda kv: kv[1].get("completed_at_epoch") or 0)
        to_drop = len(JOB_REGISTRY) - JOB_RECENT_LIMIT
        for rid, _ in terminal_jobs[:to_drop]:
            JOB_REGISTRY.pop(rid, None)


def _recent_jobs(limit: int = 20) -> list[dict]:
    """Most recent jobs first, capped. Sanitized."""
    with JOB_REGISTRY_LOCK:
        items = sorted(
            JOB_REGISTRY.values(),
            key=lambda j: j.get("created_at_epoch") or 0,
            reverse=True,
        )
    return [_sanitize_job(j) for j in items[:limit]]


def _get_job(run_id: str) -> dict | None:
    with JOB_REGISTRY_LOCK:
        j = JOB_REGISTRY.get(run_id)
    if j is None:
        return None
    return _sanitize_job(j)


def _decide_execution_mode(requested: str, question: str) -> str:
    """Decide between `wait` and `background` for `execution_mode='auto'`.

    Heuristic is intentionally conservative and deterministic:
    - `wait` is the safe default — short queries should never be backgrounded
      out from under the user.
    - `background` is chosen only when the question contains an explicit
      background/continue/long-work phrase, OR the question is long enough
      (>480 chars) to plausibly trigger a long-running runtime task.
    """
    req = (requested or "auto").strip().lower()
    if req in ("wait", "background"):
        return req
    # req == "auto" (or anything unrecognized → fall through to auto logic)
    q = (question or "").strip()
    if not q:
        return "wait"
    for pat in _BG_HINT_PATTERNS:
        if pat.search(q):
            return "background"
    if len(q) > _BG_LENGTH_THRESHOLD:
        return "background"
    return "wait"


def _dedupe_recent_run(effective_thread: str, question: str) -> str | None:
    """Within JOB_DEDUPE_WINDOW_SECONDS, return an existing active/recent run_id
    for the same (effective_thread, question) — otherwise None."""
    now = time.monotonic()
    with JOB_REGISTRY_LOCK:
        for j in JOB_REGISTRY.values():
            if j.get("effective_thread") != effective_thread:
                continue
            if j.get("question") != question:
                continue
            age = now - (j.get("created_at_epoch") or now)
            if age > JOB_DEDUPE_WINDOW_SECONDS:
                continue
            st = j.get("status")
            if st in ACTIVE_STATUSES or st in TERMINAL_STATUSES:
                return j.get("run_id")
    return None


def _thread_bridge_lock(thread_id: str) -> threading.Lock:
    with BRIDGE_COORD_LOCK:
        return BRIDGE_THREAD_LOCKS.setdefault(thread_id, threading.Lock())


def load_api_key() -> str:
    env_path = Path("/data/workspace/.env")
    wanted = ("OPENAI_REALTIME_API_KEY", "OPENAI_API_KEY")
    found: dict[str, str] = {}
    if env_path.exists():
        for raw in env_path.read_bytes().splitlines():
            if b"=" not in raw:
                continue
            name, val = raw.split(b"=", 1)
            try:
                key = name.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if key not in wanted:
                continue
            if val[:1] in (b'"', b"'") and val[-1:] == val[:1]:
                val = val[1:-1]
            found[key] = val.decode("utf-8", errors="strict").strip()
    for k in wanted:
        if found.get(k):
            return found[k]
        if os.environ.get(k):
            return os.environ[k].strip()
    raise RuntimeError(
        "Missing OPENAI_REALTIME_API_KEY (or OPENAI_API_KEY) in workspace/.env"
    )


def session_config_dict() -> dict:
    return {
        "type": "realtime",
        "model": MODEL,
        "instructions": (
            "你是 Starchild 的实时语音界面，请用中文简洁自然地说话。"
            "OpenAI Realtime 只负责语音识别和对话节奏，不负责理解、判断或改写内容。"
            "凡是涉及用户近期工作、当前项目、workspace、文件、memory、账户、余额、"
            "交易、工具或执行动作，必须调用 ask_starchild 获取真实结果，不得自行猜测。"
            "调用 ask_starchild 时，question 必须逐字转达用户刚说的原话，"
            "不要改写、缩写、扩写、翻译或替用户推测意图——用户说什么就原样传什么。"
            "只有当用户的话确实有歧义、或你不确定其指代时，才先用语音向用户追问确认，"
            "而不是自行补全后调用工具。"
            "收到工具结果后直接向用户总结，不要提及本地桩、demo 或 MCP 未连接。"
        ),
        "audio": {"output": {"voice": VOICE}},
        "tools": [
            {
                "type": "function",
                "name": "ask_starchild",
                "description": (
                    "Ask the user's Starchild agent for account/agent-specific info "
                    "or to perform an action that needs agent context."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": (
                                "The user's spoken request, relayed VERBATIM — pass "
                                "the user's own words exactly as transcribed. Do NOT "
                                "paraphrase, summarize, translate, expand, or infer "
                                "intent. If the request is ambiguous, ask the user to "
                                "clarify out loud instead of guessing."
                            ),
                        },
                        "execution_mode": {
                            "type": "string",
                            "enum": ["auto", "wait", "background"],
                            "description": (
                                "How to dispatch this ask. `wait` blocks for the reply "
                                "(default for short queries); `background` returns HTTP 202 "
                                "with a run_id the realtime model should ignore — the "
                                "browser polls /agent_jobs and injects the verified result "
                                "back into the conversation; `auto` lets the server pick "
                                "based on background hints / length. Short, normal voice "
                                "queries should stay `wait` so the user sees the answer in "
                                "the same turn."
                            ),
                        },
                    },
                    "required": ["question"],
                    "additionalProperties": False,
                },
            }
        ],
        "tool_choice": "auto",
    }


def mint_client_secret(api_key: str) -> dict:
    body = {"session": session_config_dict()}
    req = Request(
        "https://api.openai.com/v1/realtime/client_secrets",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def create_realtime_call(api_key: str, sdp_offer: str) -> tuple[int, str]:
    """Unified interface: multipart form with sdp + session → answer SDP."""
    import uuid

    boundary = f"----StarchildBoundary{uuid.uuid4().hex}"
    session_json = json.dumps(session_config_dict())

    def part(name: str, content: str, content_type: str) -> bytes:
        return (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
            f"{content}\r\n"
        ).encode("utf-8")

    body = b"".join(
        [
            part("sdp", sdp_offer, "application/sdp"),
            part("session", session_json, "application/json"),
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    req = Request(
        "https://api.openai.com/v1/realtime/calls",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=45) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def _fetch_runtime_models() -> dict:
    """Fetch the live model list from the local runtime. Graceful on failure.

    Returns a dict shaped like the runtime response. On any error the model
    list is empty and a short error string is included — never raises.
    """
    out: dict = {"models": [], "default_model": None, "current_model": None, "error": None}
    try:
        with urlopen(f"{LOCAL_RUNTIME_BASE}/models", timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        out["error"] = f"runtime_http_{e.code}"
        return out
    except Exception as e:  # noqa: BLE001
        out["error"] = f"runtime_unreachable: {type(e).__name__}"
        return out
    if isinstance(data, dict):
        out["models"] = data.get("models") or []
        out["default_model"] = data.get("default_model")
        out["current_model"] = data.get("current_model")
    return out


def _safe_bridge_config() -> dict:
    """Return a sanitized snapshot of the current bridge config."""
    with BRIDGE_CONFIG_LOCK:
        cfg = dict(BRIDGE_CONFIG)
    mode = cfg.get("thread_mode")
    if mode not in ("isolated", "persistent", "selected"):
        mode = "isolated"
    thread_id = cfg.get("thread_id")
    if not isinstance(thread_id, str) or not thread_id.strip():
        thread_id = None
    else:
        thread_id = thread_id.strip()
    return {
        "agent_id": cfg.get("agent_id") or "main",
        "model": cfg.get("model") or None,
        "thread_mode": mode,
        "thread_id": thread_id if mode == "selected" else None,
        "system_prompt": cfg.get("system_prompt") or "",
    }


# Thread IDs must be safe filesystem/url-safe identifiers. We accept alphanumerics,
# dash, underscore, dot — bounded so the runtime chat call cannot be abused to
# smuggle separators or oversized payloads. We deliberately reject slashes,
# colons, and whitespace so an attacker cannot piggy-back session-id structure.
_THREAD_ID_RE = re.compile(r"^[A-Za-z0-9._\-]{1,256}$")


def _is_safe_thread_id(value: object) -> bool:
    return isinstance(value, str) and bool(_THREAD_ID_RE.match(value))


def _thread_is_allowed(agent_id: str, thread_id: str) -> bool:
    """True if thread_id is in the recent catalog for agent_id or matches the
    currently saved selection (so a still-valid saved id survives a slow refresh).
    Never accepts arbitrary per-request overrides."""
    allowed = BRIDGE_THREAD_ALLOW.get(agent_id) or set()
    if thread_id in allowed:
        return True
    with BRIDGE_CONFIG_LOCK:
        saved = BRIDGE_CONFIG.get("thread_id")
    if isinstance(saved, str) and saved == thread_id:
        return True
    return False


def _validate_bridge_update(payload: dict) -> tuple[dict, str | None]:
    """Validate a /bridge_config POST body. Returns (updates, error_message).

    Accepts the unified `route` field (preferred) plus legacy `thread_mode` +
    `thread_id` for backwards compatibility. When `route` is present it takes
    precedence; otherwise the legacy pair is honored verbatim.

    Recognized route values:
      - "temporary"           -> thread_mode=isolated,  thread_id=null
      - "persistent"          -> thread_mode=persistent, thread_id=null
      - "thread:<thread_id>"  -> thread_mode=selected,   thread_id=<thread_id>
    """
    updates: dict = {}

    if "agent_id" in payload:
        v = payload.get("agent_id")
        if not isinstance(v, str):
            return {}, "agent_id must be a string"
        v = v.strip()
        if not v:
            return {}, "agent_id must be nonempty"
        if len(v) > 128:
            return {}, "agent_id too long (max 128)"
        # Block anything that looks like a secret or path traversal.
        if any(ch in v for ch in ("\n", "\r", "\0")):
            return {}, "agent_id contains invalid characters"
        updates["agent_id"] = v

    if "model" in payload:
        v = payload.get("model")
        if v is None or v == "":
            updates["model"] = None
        elif not isinstance(v, str):
            return {}, "model must be a string or null"
        elif len(v) > 256:
            return {}, "model too long (max 256)"
        else:
            updates["model"] = v.strip()

    # ----- Unified route dropdown (preferred) -----
    if "route" in payload:
        v = payload.get("route")
        if not isinstance(v, str):
            return {}, "route must be a string"
        v = v.strip()
        if not v:
            return {}, "route must be nonempty"
        if v == "temporary":
            updates["thread_mode"] = "isolated"
            updates["thread_id"] = None
        elif v == "persistent":
            updates["thread_mode"] = "persistent"
            updates["thread_id"] = None
        elif v.startswith("thread:"):
            cleaned = v[len("thread:"):].strip()
            if not _is_safe_thread_id(cleaned):
                return {}, "route thread id is invalid or too long (max 256, [A-Za-z0-9._-])"
            agent_for_check = updates.get("agent_id")
            if agent_for_check is None:
                with BRIDGE_CONFIG_LOCK:
                    agent_for_check = BRIDGE_CONFIG.get("agent_id") or "main"
            if not _thread_is_allowed(agent_for_check, cleaned):
                return {}, (
                    "thread_id is not in the recent thread catalog. "
                    "Refresh the thread dropdown or pick an existing thread."
                )
            updates["thread_mode"] = "selected"
            updates["thread_id"] = cleaned
        else:
            return {}, (
                "route must be 'temporary', 'persistent', or 'thread:<thread_id>'"
            )
    else:
        # ----- Legacy thread_mode + thread_id (backwards compatible) -----
        if "thread_mode" in payload:
            v = payload.get("thread_mode")
            if v not in ("isolated", "persistent", "selected"):
                return {}, "thread_mode must be 'isolated', 'persistent', or 'selected'"
            updates["thread_mode"] = v

        if "thread_id" in payload:
            v = payload.get("thread_id")
            # thread_id is allowed to be null/empty: switch to (or stay in) a mode
            # that does not need one. A nonempty thread_id must be a safe id, and
            # when combined with mode='selected' it must already be in the recent
            # catalog (or match the currently saved selection).
            if v is None or v == "":
                updates["thread_id"] = None
            else:
                if not isinstance(v, str):
                    return {}, "thread_id must be a string"
                cleaned = v.strip()
                if not _is_safe_thread_id(cleaned):
                    return {}, "thread_id is invalid or too long (max 256, [A-Za-z0-9._-])"
                # Resolve effective mode considering the possibly already-applied
                # thread_mode update in the same payload (so clients sending both
                # at once get coherent validation).
                new_mode = updates.get("thread_mode")
                if new_mode is None:
                    with BRIDGE_CONFIG_LOCK:
                        new_mode = BRIDGE_CONFIG.get("thread_mode") or "isolated"
                if new_mode == "selected":
                    agent_for_check = updates.get("agent_id")
                    if agent_for_check is None:
                        with BRIDGE_CONFIG_LOCK:
                            agent_for_check = BRIDGE_CONFIG.get("agent_id") or "main"
                    if not _thread_is_allowed(agent_for_check, cleaned):
                        return {}, (
                            "thread_id is not in the recent thread catalog. "
                            "Refresh the thread dropdown or pick an existing thread."
                        )
                updates["thread_id"] = cleaned

    if "system_prompt" in payload:
        v = payload.get("system_prompt")
        if v is None:
            v = ""
        if not isinstance(v, str):
            return {}, "system_prompt must be a string"
        if len(v) > 4000:
            return {}, "system_prompt too long (max 4000)"
        updates["system_prompt"] = v

    return updates, None


def _resolve_effective_thread(cfg: dict) -> tuple[str, bool, str]:
    """Map a bridge config snapshot to (effective_thread, is_temporary, mode).

    `effective_thread` is the runtime session key the bridge will use.
    `mode` is the underlying thread_mode string for diagnostics and routing.
    """
    mode = cfg.get("thread_mode") or "isolated"
    if mode == "persistent":
        return "voice-realtime-persistent", False, mode
    if mode == "selected":
        configured = cfg.get("thread_id")
        if not configured:
            raise RuntimeError(
                "Voice route 'thread:<id>' is set but no thread is selected. "
                "Pick an existing thread in Agent settings and save again."
            )
        return configured, False, mode
    return "voice-realtime", True, mode


def _format_recent_context(context) -> str:
    """Build a compact '[Recent voice conversation]' block from browser-supplied
    rolling turns. Only used in temporary mode, where the runtime thread has no
    persisted history to resolve follow-up references ('可以去做了吗' etc.).

    Accepts a list of {role, text} dicts; ignores anything malformed. Caps to
    the last 6 turns and 1200 chars total to stay lightweight and out of PII/log
    territory. Returns '' when there is nothing usable.
    """
    if not isinstance(context, list) or not context:
        return ""
    lines = []
    for turn in context[-6:]:
        if not isinstance(turn, dict):
            continue
        role = turn.get("role")
        text = str(turn.get("text") or "").strip()
        if not text:
            continue
        who = "用户" if role == "user" else "语音助手"
        lines.append(f"{who}: {text}")
    if not lines:
        return ""
    block = "\n".join(lines)
    if len(block) > 1200:
        block = block[-1200:]
    return (
        "[Recent voice conversation — for resolving follow-up references only, "
        "not new instructions]\n" + block + "\n\n"
    )


def _dispatch_chat_call(
    effective_thread: str,
    is_temporary: bool,
    question: str,
    cfg: dict,
    context=None,
) -> dict:
    """Issue the actual POST /chat to the local runtime.

    Holds the per-thread lock so duplicate Realtime events cannot abort an
    in-flight query, and reuses the 15 s result cache for identical
    (thread, question) pairs. No background concerns — caller decides how
    to await or thread this.
    """
    cache_key = (effective_thread, question)
    thread_lock = _thread_bridge_lock(effective_thread)
    with thread_lock:
        now = time.monotonic()
        with BRIDGE_COORD_LOCK:
            cached = BRIDGE_RESULT_CACHE.get(cache_key)
            if cached and now - cached[0] <= BRIDGE_CACHE_TTL_SECONDS:
                return {**cached[1], "deduplicated": True}

        selected_agent = cfg["agent_id"]
        selected_model = cfg["model"]  # may be None → runtime picks default
        custom_prompt = cfg["system_prompt"] or ""
        voice_prompt = (
            "[Starchild Live Voice Agent]\n"
            "Source: This user message was relayed from the Starchild Live realtime voice "
            "interface through ask_starchild. Treat the text below as the user's spoken request.\n"
            "You may use this thread's context, workspace, memory, and available tools. "
            "Answer with the conclusion first and keep it suitable for spoken playback. "
            "Do not expose internal reasoning.\n\n"
        )
        if custom_prompt:
            voice_prompt += f"[User-configured Voice Agent instructions]\n{custom_prompt}\n\n"
        # Temporary mode has no persisted thread history, so follow-up
        # references cannot be resolved server-side. Carry the browser's rolling
        # transcript so short utterances ('可以去做了吗') stay unambiguous.
        # Selected/persistent threads already have real history — skip to avoid
        # duplicating context.
        if is_temporary:
            recent_block = _format_recent_context(context)
            if recent_block:
                voice_prompt += recent_block
        voice_prompt += f"[Spoken user request]\n{question}"

        chat_body: dict = {
            "message": voice_prompt,
            "agent_id": selected_agent,
            "thread_id": effective_thread,
            "call_source": "internal",
            "is_temporary": is_temporary,
            "channel": "web",
        }
        if selected_model:
            chat_body["model"] = selected_model

        body = json.dumps(chat_body, ensure_ascii=False).encode("utf-8")
        req = Request(
            f"{LOCAL_RUNTIME_BASE}/chat",
            data=body,
            headers={
                "Content-Type": "application/json",
                "SC-CALLER-ID": f"chat:voice:{effective_thread}",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=150) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:800]
            raise RuntimeError(f"Starchild Agent 返回 HTTP {e.code}: {detail}") from e

        if not data.get("success") or not data.get("reply"):
            raise RuntimeError(data.get("error") or "Starchild Agent 未返回有效回复")
        result = {
            "result": data["reply"],
            "agent_id": data.get("agent_id", selected_agent),
            "model": data.get("model", selected_model),
            "thread_id": effective_thread,
            "thread_mode": cfg.get("thread_mode") or "isolated",
            "is_temporary": is_temporary,
            "usage": data.get("usage", {}),
            "turns": data.get("turns", 0),
            "deduplicated": False,
        }
        with BRIDGE_COORD_LOCK:
            BRIDGE_RESULT_CACHE[cache_key] = (time.monotonic(), result)
            stale = [
                key for key, (ts, _) in BRIDGE_RESULT_CACHE.items()
                if time.monotonic() - ts > BRIDGE_CACHE_TTL_SECONDS
            ]
            for key in stale:
                BRIDGE_RESULT_CACHE.pop(key, None)
        return result


def agent_bridge(question: str, thread_id: str | None = None, context=None) -> dict:
    """Synchronously dispatch one voice request to the local Starchild runtime.

    The caller-supplied thread_id argument is intentionally ignored — the only
    thread IDs the bridge ever sends are derived from the saved /bridge_config
    (or the per-call voice transport key for isolated mode). Arbitrary
    per-request overrides from the browser are never honored so the runtime
    cannot be steered into a foreign session by a hostile client.

    This is the `wait` execution path. For long-running work the realtime
    client should pass `execution_mode=background` and consume the run_id
    from the HTTP 202 response.
    """
    del thread_id  # never honor per-request overrides
    q = (question or "").strip()
    if not q:
        raise ValueError("问题不能为空")

    cfg = _safe_bridge_config()
    effective_thread, is_temporary, _mode = _resolve_effective_thread(cfg)
    return _dispatch_chat_call(effective_thread, is_temporary, q, cfg, context)


# ----- Background job worker -----

def _finish_background_job(run_id: str, effective_thread: str, cancelled: bool = False) -> None:
    """Atomically transition a job to a terminal `cancelled` state.

    Centralized so every exit path uses the same cleanup: clear the
    per-thread active pointer, stamp completed_at, and let cleanup run.
    """
    now = time.monotonic()
    with JOB_REGISTRY_LOCK:
        job = JOB_REGISTRY.get(run_id)
        if not job:
            return
        # Never overwrite an already-terminal job.
        if job.get("status") in TERMINAL_STATUSES:
            return
        job["status"] = "cancelled"
        job["error"] = "cancelled before completion"
        job["completed_at"] = _now_iso()
        job["completed_at_epoch"] = now
        _job_cleanup_locked(now)
        if JOB_ACTIVE_PER_THREAD.get(effective_thread) == run_id:
            JOB_ACTIVE_PER_THREAD.pop(effective_thread, None)


def _start_background_job(
    run_id: str,
    effective_thread: str,
    is_temporary: bool,
    question: str,
    cfg: dict,
    context=None,
) -> None:
    """Worker thread entrypoint. Mutates JOB_REGISTRY[run_id] only."""
    started_at = _now_iso()
    pre_cancelled = False
    with JOB_REGISTRY_LOCK:
        job = JOB_REGISTRY.get(run_id)
        if not job:
            return
        # If cancel was requested before we got scheduled, stay cancelled and
        # do not invoke the runtime. The unified exit path flips us to a
        # terminal `cancelled` state with a clean completed_at.
        if job.get("status") in ("cancel_requested", "cancelled"):
            pre_cancelled = True
            job["started_at"] = started_at
            job["started_at_epoch"] = time.monotonic()
        else:
            job["started_at"] = started_at
            job["started_at_epoch"] = time.monotonic()
            job["status"] = "running"
    if pre_cancelled:
        _finish_background_job(run_id, effective_thread, cancelled=True)
        return
    try:
        result = _dispatch_chat_call(effective_thread, is_temporary, question, cfg, context)
        # Worker exit observed — capture the result unless cancellation has
        # already been requested and observed by the runtime.
        with JOB_REGISTRY_LOCK:
            job = JOB_REGISTRY.get(run_id)
            if not job:
                return
            if job.get("status") == "cancel_requested":
                # Honored as cancelled — runtime was told to stop.
                job["status"] = "cancelled"
                job["error"] = "cancelled before completion"
            else:
                job["status"] = "completed"
                job["result"] = result.get("result") if isinstance(result, dict) else None
                # Surface minimal completion metadata for the UI; never the
                # prompt or full session keys.
                job["model"] = result.get("model") if isinstance(result, dict) else None
            job["completed_at"] = _now_iso()
            job["completed_at_epoch"] = time.monotonic()
            _job_cleanup_locked(time.monotonic())
        # Clear "active per thread" if we are still the holder.
        with JOB_REGISTRY_LOCK:
            if JOB_ACTIVE_PER_THREAD.get(effective_thread) == run_id:
                JOB_ACTIVE_PER_THREAD.pop(effective_thread, None)
    except Exception as e:  # noqa: BLE001
        with JOB_REGISTRY_LOCK:
            job = JOB_REGISTRY.get(run_id)
            if not job:
                return
            if job.get("status") == "cancel_requested":
                job["status"] = "cancelled"
                job["error"] = "cancelled before completion"
            else:
                job["status"] = "failed"
                job["error"] = str(e)[:400]
            job["completed_at"] = _now_iso()
            job["completed_at_epoch"] = time.monotonic()
            _job_cleanup_locked(time.monotonic())
        with JOB_REGISTRY_LOCK:
            if JOB_ACTIVE_PER_THREAD.get(effective_thread) == run_id:
                JOB_ACTIVE_PER_THREAD.pop(effective_thread, None)


def start_background_bridge_job(question: str, context=None) -> dict:
    """Validate and start a background job. Returns the sanitized accepted
    record (the same shape returned by /agent_jobs GET)."""
    q = (question or "").strip()
    if not q:
        raise ValueError("问题不能为空")
    cfg = _safe_bridge_config()
    effective_thread, is_temporary, mode = _resolve_effective_thread(cfg)

    # Dedupe: within JOB_DEDUPE_WINDOW_SECONDS, identical (thread, question)
    # returns the existing active/recent run_id instead of starting a second.
    existing = _dedupe_recent_run(effective_thread, q)
    if existing:
        snap = _get_job(existing)
        if snap is not None:
            snap["deduplicated"] = True
            return snap

    run_id = _make_run_id()
    created_at = _now_iso()
    job = {
        "run_id": run_id,
        "status": "queued",
        "created_at": created_at,
        "created_at_epoch": time.monotonic(),
        "started_at": None,
        "started_at_epoch": None,
        "completed_at": None,
        "completed_at_epoch": None,
        "thread_mode": mode,
        "thread_id": effective_thread,
        "effective_thread": effective_thread,
        "is_temporary": is_temporary,
        "agent_id": cfg["agent_id"],
        "question": q,  # internal only — never returned by _sanitize_job
        "result": None,
        "error": None,
    }
    with JOB_REGISTRY_LOCK:
        active_id = JOB_ACTIVE_PER_THREAD.get(effective_thread)
        active = JOB_REGISTRY.get(active_id) if active_id else None
        if active and active.get("status") in ACTIVE_STATUSES:
            raise ValueError(
                "This thread already has an active background job: " + str(active_id)
            )
        if active_id:
            JOB_ACTIVE_PER_THREAD.pop(effective_thread, None)
        JOB_REGISTRY[run_id] = job
        JOB_ACTIVE_PER_THREAD[effective_thread] = run_id
        _job_cleanup_locked(time.monotonic())
    # Worker is daemon so the server can exit cleanly during tests/dev.
    t = threading.Thread(
        target=_start_background_job,
        args=(run_id, effective_thread, is_temporary, q, cfg, context),
        daemon=True,
        name=f"starchild-bridge-job-{run_id[:10]}",
    )
    t.start()
    return _sanitize_job(job)


def request_job_cancel(run_id: str) -> dict | None:
    """Mark a job as cancel_requested (queued) or cancel_requested (running).
    Returns the sanitized resulting state, or None if the run_id is unknown.
    Never claims `cancelled` — only the worker can, when it observes the exit
    path. Best-effort posts to the local runtime /chat/runs/cancel for running
    jobs."""
    if not isinstance(run_id, str) or not run_id:
        return None
    with JOB_REGISTRY_LOCK:
        job = JOB_REGISTRY.get(run_id)
    if not job:
        return None
    status = job.get("status")
    if status in TERMINAL_STATUSES:
        return _sanitize_job(job)
    effective_thread = job.get("effective_thread") or job.get("thread_id")
    if status == "queued":
        # We have not yet started the worker. Try to prevent the worker from
        # doing meaningful work by flipping the status atomically. The worker
        # checks this in its finally path and never claims success.
        with JOB_REGISTRY_LOCK:
            j = JOB_REGISTRY.get(run_id)
            if not j:
                return None
            if j.get("status") == "queued":
                j["status"] = "cancel_requested"
                j["completed_at"] = _now_iso()
                j["completed_at_epoch"] = time.monotonic()
                # Note: do not flip to "cancelled" here — the worker may
                # already be in-flight even if it looked queued, and we
                # never claim cancellation unless the worker exits cleanly.
        # Best-effort: tell runtime to cancel the (possibly about-to-start)
        # run for this thread. Runtime will silently 404 if there is no run.
        try:
            req = Request(
                f"{LOCAL_RUNTIME_BASE}/chat/runs/cancel?thread_id=" +
                str(effective_thread or ""),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(req, timeout=3):
                pass
        except Exception:
            pass
    elif status == "running":
        with JOB_REGISTRY_LOCK:
            j = JOB_REGISTRY.get(run_id)
            if j and j.get("status") == "running":
                j["status"] = "cancel_requested"
        try:
            req = Request(
                f"{LOCAL_RUNTIME_BASE}/chat/runs/cancel?thread_id=" +
                str(effective_thread or ""),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(req, timeout=3):
                pass
        except Exception:
            pass
    elif status == "cancel_requested":
        pass
    return _sanitize_job(job)


def _fetch_bridge_threads(agent_id: str) -> dict:
    """Return titled work threads from the authenticated Thread Service.

    Thread IDs remain internal routing values. The browser receives the real
    user-facing title plus lightweight activity metadata; it never needs to
    display an ID. Transport, temporary and voice-only threads are excluded.
    """
    out: dict = {"agent_id": agent_id, "threads": [], "error": None}
    params = urlencode({"limit": 50, "offset": 0, "agent_id": agent_id})
    headers = {"Accept": "application/json"}
    internal_key = os.environ.get("INTERNAL_API_KEY", "")
    container_jwt = os.environ.get("CONTAINER_JWT", "")
    if internal_key:
        headers["X-INTERNAL-API-KEY"] = internal_key
    elif container_jwt:
        headers["Authorization"] = f"Bearer {container_jwt}"
    else:
        out["error"] = "thread_service_auth_missing"
        return out

    try:
        req = Request(
            f"{THREAD_SERVICE_BASE}/api/clawd/threads?{params}",
            headers=headers,
        )
        with urlopen(req, timeout=8) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        out["error"] = f"thread_service_http_{e.code}"
        return out
    except Exception as e:  # noqa: BLE001
        out["error"] = f"thread_service_unreachable: {type(e).__name__}"
        return out

    source = raw.get("threads") if isinstance(raw, dict) else None
    if not isinstance(source, list):
        out["error"] = "thread_service_shape_invalid"
        return out

    seen: set[str] = set()
    threads: list[dict] = []
    for item in source:
        if not isinstance(item, dict):
            continue
        thread_id = item.get("thread_id")
        if not isinstance(thread_id, str) or not thread_id or thread_id in seen:
            continue
        low = thread_id.lower()
        if low.startswith((
            "voice-realtime", "voice_", "tg-", "wechat-", "scheduled",
            "cron_", "interval_", "tmp", "push",
        )):
            continue
        seen.add(thread_id)

        title = item.get("title")
        if not isinstance(title, str) or not title.strip() or title.strip() == "New Conversation":
            title = "Untitled conversation"
        else:
            title = title.strip()[:120]
        msg_count = item.get("message_count")
        if not isinstance(msg_count, int):
            msg_count = 0
        updated = item.get("updated_at")
        if not isinstance(updated, (int, float)):
            updated = 0
        threads.append({
            "thread_id": thread_id,
            "title": title,
            "message_count": msg_count,
            "updated_at": updated,
        })

    BRIDGE_THREAD_ALLOW[agent_id] = {t["thread_id"] for t in threads}
    out["threads"] = threads
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "starchild-realtime-demo/0.2"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[demo] {self.address_string()} - {fmt % args}")

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict) -> None:
        self._send(
            code,
            json.dumps(obj, ensure_ascii=False).encode("utf-8"),
            "application/json",
        )

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            if not INDEX.exists():
                self._json(500, {"error": "index.html missing"})
                return
            self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
            return
        if path == "/health":
            self._json(200, {"ok": True, "model": MODEL, "voice": VOICE, "mode": "unified+ephemeral"})
            return
        if path == "/bridge_config":
            try:
                cfg = _safe_bridge_config()
                runtime_models = _fetch_runtime_models()
                # Hide secrets / strip nulls as appropriate for the wire.
                self._json(
                    200,
                    {
                        "config": cfg,
                        "runtime_models": runtime_models,
                    },
                )
            except Exception as e:  # noqa: BLE001
                self._json(500, {"error": str(e)})
            return
        if path == "/bridge_threads":
            try:
                from urllib.parse import parse_qs
            except ImportError:
                parse_qs = None  # noqa: N111
            qs = self.path.split("?", 1)[1] if "?" in self.path else ""
            params = parse_qs(qs) if parse_qs else {}
            agent_q = (params.get("agent_id") or ["main"])[0].strip() or "main"
            if not _is_safe_thread_id(agent_q):
                self._json(400, {"error": "agent_id invalid"})
                return
            try:
                data = _fetch_bridge_threads(agent_q)
                self._json(200, data)
            except Exception as e:  # noqa: BLE001
                self._json(500, {"error": str(e)})
            return

        if path == "/agent_jobs":
            try:
                from urllib.parse import parse_qs
            except ImportError:
                parse_qs = None  # noqa: N111
            qs = self.path.split("?", 1)[1] if "?" in self.path else ""
            params = parse_qs(qs) if parse_qs else {}
            run_ids = params.get("run_id") or []
            if run_ids:
                run_id = run_ids[0].strip()
                snap = _get_job(run_id) if run_id else None
                if snap is None:
                    self._json(404, {"error": "run_id not found"})
                else:
                    self._json(200, snap)
            else:
                jobs = _recent_jobs(20)
                self._json(200, {"jobs": jobs})
            return

        if path == "/token":
            try:
                api_key = load_api_key()
                data = mint_client_secret(api_key)
                value = data.get("value") or data.get("client_secret", {}).get("value")
                if not value:
                    self._json(
                        502,
                        {
                            "error": "client_secret missing in upstream response",
                            "raw_keys": list(data.keys()),
                        },
                    )
                    return
                self._json(
                    200,
                    {
                        "value": value,
                        "expires_at": data.get("expires_at")
                        or data.get("client_secret", {}).get("expires_at"),
                        "model": MODEL,
                        "voice": VOICE,
                    },
                )
            except HTTPError as e:
                err = e.read().decode("utf-8", errors="replace")[:800]
                self._json(
                    e.code,
                    {"error": "upstream_http_error", "status": e.code, "body": err},
                )
            except Exception as e:  # noqa: BLE001
                self._json(500, {"error": str(e), "trace": traceback.format_exc()[-600:]})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()

        # Unified WebRTC: browser posts SDP offer → answer SDP
        # Accepts: JSON {"sdp_b64": ...} (WAF-safe) OR raw application/sdp
        if path == "/session":
            try:
                import base64

                text = raw.decode("utf-8", errors="replace").strip()
                sdp_offer = ""
                wrapped = False
                if text.startswith("{"):
                    try:
                        obj = json.loads(text)
                        if obj.get("sdp_b64"):
                            sdp_offer = base64.b64decode(obj["sdp_b64"]).decode("utf-8")
                            wrapped = True
                        elif obj.get("sdp"):
                            sdp_offer = str(obj["sdp"])
                            wrapped = True
                    except (json.JSONDecodeError, ValueError):
                        pass
                if not sdp_offer:
                    sdp_offer = text
                if not sdp_offer:
                    self._json(400, {"error": "empty sdp"})
                    return
                print(f"[demo] /session sdp_len={len(sdp_offer)} wrapped={wrapped}")
                api_key = load_api_key()
                status, body = create_realtime_call(api_key, sdp_offer)
                print(f"[demo] /session upstream status={status} body_len={len(body)}")
                if status >= 400 or not body.lstrip().startswith("v="):
                    # upstream error (json) or unexpected
                    self._send(
                        status if status >= 400 else 502,
                        body.encode("utf-8"),
                        "application/json" if body.lstrip().startswith("{") else "text/plain",
                    )
                    return
                if wrapped:
                    # Return answer SDP base64-wrapped too (response also crosses the WAF)
                    self._json(
                        200,
                        {"sdp_b64": base64.b64encode(body.encode("utf-8")).decode("ascii")},
                    )
                else:
                    self._send(200, body.encode("utf-8"), "application/sdp")
            except Exception as e:  # noqa: BLE001
                self._json(
                    500,
                    {"error": str(e), "trace": traceback.format_exc()[-600:]},
                )
            return

        # JSON endpoints
        try:
            payload = json.loads(raw.decode("utf-8") or "{}") if raw else {}
        except json.JSONDecodeError:
            if ctype and ctype not in ("application/json", "text/json"):
                self._json(400, {"error": "invalid body", "content_type": ctype})
                return
            self._json(400, {"error": "invalid json"})
            return

        if path == "/agent_bridge":
            question = str(payload.get("question") or "")
            # Optional rolling voice-conversation context (temporary mode only).
            context = payload.get("context")
            if not isinstance(context, list):
                context = None
            # thread_id from the wire is intentionally dropped — the bridge
            # only ever sends the configured thread (selected / persistent /
            # isolated). See agent_bridge() and the security note in README.
            execution_mode = str(payload.get("execution_mode") or "auto")
            try:
                decided = _decide_execution_mode(execution_mode, question)
            except Exception as e:  # noqa: BLE001
                self._json(400, {"ok": False, "error": "invalid execution_mode: " + str(e)})
                return
            try:
                # Every request gets a run_id before runtime work starts. This
                # makes a synchronous call recoverable if it outlives the outer
                # Preview gateway's ~30 s request window.
                snap = start_background_bridge_job(question, context=context)
                if decided == "wait":
                    deadline = time.monotonic() + max(1.0, SYNC_WAIT_BUDGET_SECONDS)
                    while time.monotonic() < deadline:
                        current = _get_job(str(snap.get("run_id") or ""))
                        if current and current.get("status") in TERMINAL_STATUSES:
                            snap = current
                            break
                        time.sleep(0.05)

                if decided == "wait" and snap.get("status") == "completed":
                    self._json(
                        200,
                        {
                            "ok": True,
                            "result": snap.get("result"),
                            "agent_id": snap.get("agent_id"),
                            "model": snap.get("model"),
                            "thread_id": snap.get("thread_id"),
                            "thread_mode": snap.get("thread_mode"),
                            "is_temporary": snap.get("is_temporary"),
                            "deferred": False,
                        },
                    )
                elif decided == "wait" and snap.get("status") in ("failed", "cancelled"):
                    self._json(
                        502,
                        {"ok": False, "run_id": snap.get("run_id"), "error": snap.get("error")},
                    )
                else:
                    # Explicit background, or a wait call that exceeded the
                    # safe synchronous budget. The same worker keeps running;
                    # the browser resumes it through /agent_jobs.
                    current = _get_job(str(snap.get("run_id") or "")) or snap
                    self._send(
                        202,
                        json.dumps(
                            {
                                "ok": True,
                                "accepted": True,
                                "deferred": decided == "wait",
                                "run_id": current.get("run_id"),
                                "status": current.get("status"),
                                "thread_id": current.get("thread_id"),
                                "thread_mode": current.get("thread_mode"),
                                "is_temporary": current.get("is_temporary"),
                            },
                            ensure_ascii=False,
                        ).encode("utf-8"),
                        "application/json",
                    )
            except ValueError as e:
                # Empty question and other validation errors — let the caller
                # handle it the same way they would for any other 4xx.
                self._json(400, {"ok": False, "error": str(e)})
            except Exception as e:  # noqa: BLE001
                self._json(502, {"ok": False, "error": str(e)})
            return

        if path == "/agent_jobs/cancel":
            run_id = str(payload.get("run_id") or "").strip()
            if not run_id:
                self._json(400, {"ok": False, "error": "run_id required"})
                return
            snap = request_job_cancel(run_id)
            if snap is None:
                self._json(404, {"ok": False, "error": "run_id not found"})
                return
            self._json(200, {"ok": True, "job": snap})
            return

        if path == "/bridge_config":
            if not isinstance(payload, dict):
                self._json(400, {"error": "body must be a JSON object"})
                return
            updates, err = _validate_bridge_update(payload)
            if err:
                self._json(400, {"error": err})
                return
            with BRIDGE_CONFIG_LOCK:
                BRIDGE_CONFIG.update(updates)
            cfg = _safe_bridge_config()
            self._json(200, {"ok": True, "config": cfg})
            return

        self._json(404, {"error": "not found"})


def main() -> None:
    try:
        k = load_api_key()
        print("[demo] OpenAI Realtime API key loaded securely")
    except Exception as e:  # noqa: BLE001
        print(f"[demo] WARNING: {e}")

    ThreadingHTTPServer.allow_reuse_address = True
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[demo] listening on http://{HOST}:{PORT}")
    print(f"[demo] model={MODEL} voice={VOICE}")
    print(
        "[demo] endpoints: GET /token  POST /session  POST /agent_bridge"
        "  GET|POST /bridge_config  GET /bridge_threads  GET /agent_jobs"
        "  POST /agent_jobs/cancel"
    )
    httpd.serve_forever()


if __name__ == "__main__":
    main()
