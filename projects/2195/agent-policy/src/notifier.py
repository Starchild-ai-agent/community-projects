# -*- coding: utf-8 -*-
"""
Telegram approval loop for ESCALATE decisions.

Sends a structured message with Approve / Deny buttons.
Blocks until answered or timeout. Thread-safe.

Env vars:
  POLICY_TG_BOT_TOKEN
  POLICY_TG_CHAT_ID
"""
from __future__ import annotations
import hashlib, logging, os, threading, time
from dataclasses import dataclass
from typing import Optional
import requests
from policy import Decision, Verdict

log = logging.getLogger("policy.notifier")
_BASE = "https://api.telegram.org"

def _tg(token: str, method: str, **kw) -> dict:
    try:
        r = requests.post(f"{_BASE}/bot{token}/{method}", json=kw, timeout=10)
        return r.json()
    except Exception as e:
        log.warning("TG API %s: %s", method, e); return {}

@dataclass
class ApprovalResult:
    approved: bool
    timeout:  bool = False
    by:       str  = ""

class TelegramNotifier:
    """
    on_timeout: "deny" (default, safe) | "allow" (opt-in)
    """
    def __init__(self, bot_token=None, chat_id=None,
                 timeout_seconds=300, on_timeout="deny"):
        self.token      = bot_token or os.environ["POLICY_TG_BOT_TOKEN"]
        self.chat_id    = chat_id   or os.environ["POLICY_TG_CHAT_ID"]
        self.timeout    = timeout_seconds
        self.on_timeout = on_timeout
        self._pending: dict[str, threading.Event] = {}
        self._results:  dict[str, bool]           = {}
        threading.Thread(target=self._poll_loop, daemon=True).start()

    def request_approval(self, decision: Decision) -> ApprovalResult:
        nonce = hashlib.sha256(
            f"{decision.action}{decision.reason}{time.time()}".encode()
        ).hexdigest()[:12]
        text = (
            f"🔐 *Policy escalation* `[{nonce}]`\n\n"
            f"Action: `{decision.action}`\n"
            f"Rule: `{decision.rule}`\n"
            f"Reason: {decision.reason}\n\n"
            f"Approve or deny within {self.timeout//60} min — default *DENY*."
        )
        kb = {"inline_keyboard": [[
            {"text": "✅ Approve", "callback_data": f"APPROVE:{nonce}"},
            {"text": "❌ Deny",    "callback_data": f"DENY:{nonce}"},
        ]]}
        _tg(self.token, "sendMessage", chat_id=self.chat_id,
            text=text, parse_mode="Markdown", reply_markup=kb)
        ev = threading.Event()
        self._pending[nonce] = ev
        signalled = ev.wait(timeout=self.timeout)
        if not signalled:
            self._pending.pop(nonce, None)
            approved = (self.on_timeout == "allow")
            self.notify(f"⏱ `{nonce}` timed out — {'ALLOWED' if approved else 'DENIED'} by default.")
            return ApprovalResult(approved=approved, timeout=True)
        return ApprovalResult(approved=self._results.pop(nonce, False))

    def notify(self, text: str, parse_mode="Markdown"):
        _tg(self.token, "sendMessage", chat_id=self.chat_id,
            text=text, parse_mode=parse_mode)

    def _poll_loop(self):
        offset = 0
        while True:
            try:
                resp = _tg(self.token, "getUpdates",
                           offset=offset, timeout=30,
                           allowed_updates=["callback_query"])
                for upd in resp.get("result", []):
                    offset = upd["update_id"] + 1
                    cq = upd.get("callback_query"); 
                    if not cq: continue
                    _tg(self.token, "answerCallbackQuery", callback_query_id=cq["id"])
                    data = cq.get("data", "")
                    if ":" not in data: continue
                    verdict, nonce = data.split(":", 1)
                    if nonce not in self._pending: continue
                    self._results[nonce] = (verdict == "APPROVE")
                    ev = self._pending.pop(nonce, None)
                    if ev: ev.set()
                    who = cq.get("from", {}).get("username", "?")
                    emoji = "✅" if verdict == "APPROVE" else "❌"
                    self.notify(f"{emoji} `{nonce}` {'approved' if verdict=='APPROVE' else 'denied'} by @{who}")
            except Exception as e:
                log.warning("poll loop: %s", e); time.sleep(5)
