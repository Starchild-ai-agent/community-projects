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
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
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
    "thread_mode": "isolated",  # 'isolated' | 'persistent'
    "system_prompt": "",
}
BRIDGE_CONFIG_LOCK = threading.Lock()
LOCAL_RUNTIME_BASE = os.environ.get("STARCHILD_RUNTIME_URL", "http://127.0.0.1:8000")

# The runtime allows one active run per session key. Realtime may emit duplicate
# completion events (and multiple browser tabs may share a voice thread), so
# serialize bridge calls per effective thread. Identical requests are reused for
# a short window after the first caller completes.
BRIDGE_COORD_LOCK = threading.Lock()
BRIDGE_THREAD_LOCKS: dict[str, threading.Lock] = {}
BRIDGE_RESULT_CACHE: dict[tuple[str, str], tuple[float, dict]] = {}
BRIDGE_CACHE_TTL_SECONDS = 15.0


def _thread_bridge_lock(thread_id: str) -> threading.Lock:
    with BRIDGE_COORD_LOCK:
        return BRIDGE_THREAD_LOCKS.setdefault(thread_id, threading.Lock())


def load_api_key() -> str:
    wanted = ("OPENAI_REALTIME_API_KEY", "OPENAI_API_KEY")
    # 1. Environment variables win — already-exported shell vars take precedence.
    for k in wanted:
        if os.environ.get(k):
            return os.environ[k].strip()
    # 2. Search relative .env paths (project-local, then cwd). No machine-specific paths.
    env_candidates = [
        Path(__file__).resolve().parent.parent / ".env",
        Path.cwd() / ".env",
    ]
    for env_path in env_candidates:
        if not env_path.exists():
            continue
        found: dict[str, str] = {}
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
    raise RuntimeError(
        "Missing OPENAI_REALTIME_API_KEY (or OPENAI_API_KEY). "
        "Set it in the environment or in a .env at the project root."
    )


def session_config_dict() -> dict:
    return {
        "type": "realtime",
        "model": MODEL,
        "instructions": (
            "你是 Starchild 的实时语音界面，请用中文简洁自然地说话。"
            "OpenAI Realtime 只负责语音和对话节奏。凡是涉及用户近期工作、"
            "当前项目、workspace、文件、memory、账户、余额、交易、工具或执行动作，"
            "必须调用 ask_starchild 获取真实结果，不得自行猜测。"
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
                            "description": "What to ask or do via the Starchild agent",
                        }
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
    return {
        "agent_id": cfg.get("agent_id") or "main",
        "model": cfg.get("model") or None,
        "thread_mode": cfg.get("thread_mode") if cfg.get("thread_mode") in ("isolated", "persistent") else "isolated",
        "system_prompt": cfg.get("system_prompt") or "",
    }


def _validate_bridge_update(payload: dict) -> tuple[dict, str | None]:
    """Validate a /bridge_config POST body. Returns (updates, error_message)."""
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

    if "thread_mode" in payload:
        v = payload.get("thread_mode")
        if v not in ("isolated", "persistent"):
            return {}, "thread_mode must be 'isolated' or 'persistent'"
        updates["thread_mode"] = v

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


def agent_bridge(question: str, thread_id: str = "voice-realtime") -> dict:
    """Send one serialized voice request to the local Starchild runtime."""
    q = (question or "").strip()
    if not q:
        raise ValueError("问题不能为空")

    cfg = _safe_bridge_config()
    selected_agent = cfg["agent_id"]
    selected_model = cfg["model"]  # may be None → runtime picks default
    custom_prompt = cfg["system_prompt"] or ""

    if cfg["thread_mode"] == "persistent":
        effective_thread = "voice-realtime-persistent"
        is_temporary = False
    else:
        effective_thread = (thread_id or "").strip() or "voice-realtime"
        is_temporary = True

    # The Agent runtime replaces an active run when another request uses the
    # same session key. Hold a per-thread lock so duplicate Realtime events or
    # multiple tabs cannot abort an in-flight query.
    cache_key = (effective_thread, q)
    thread_lock = _thread_bridge_lock(effective_thread)
    with thread_lock:
        now = time.monotonic()
        with BRIDGE_COORD_LOCK:
            cached = BRIDGE_RESULT_CACHE.get(cache_key)
            if cached and now - cached[0] <= BRIDGE_CACHE_TTL_SECONDS:
                return {**cached[1], "deduplicated": True}

        voice_prompt = (
            "[语音入口请求]\n"
            "请处理下面的用户请求。你可以读取当前 workspace、memory 并调用已有工具。"
            "最终回答请先直接给结论，适合语音朗读，尽量简洁；不要暴露内部思考过程。\n\n"
        )
        if custom_prompt:
            voice_prompt += f"[用户自定义系统提示]\n{custom_prompt}\n\n"
        voice_prompt += f"用户请求：{q}"

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
            "thread_mode": cfg["thread_mode"],
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
            thread_id = str(payload.get("thread_id") or "voice-realtime")
            try:
                result = agent_bridge(question, thread_id)
                self._json(200, {"ok": True, **result})
            except Exception as e:  # noqa: BLE001
                self._json(502, {"ok": False, "error": str(e)})
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
        print(f"[demo] api key loaded (len={len(k)}, prefix={k[:8]}...)")
    except Exception as e:  # noqa: BLE001
        print(f"[demo] WARNING: {e}")

    ThreadingHTTPServer.allow_reuse_address = True
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[demo] listening on http://{HOST}:{PORT}")
    print(f"[demo] model={MODEL} voice={VOICE}")
    print("[demo] endpoints: GET /token  POST /session  POST /agent_bridge  GET|POST /bridge_config")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
