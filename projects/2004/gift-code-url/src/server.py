#!/usr/bin/env python3
"""Gift-code URL claim server.

Each visitor gets a unique code from the pool, handed out in order.
A visitor is identified by a `cid` (random UUID kept in localStorage), so
re-opening the page returns the SAME code instead of burning a new one.

When the pool runs out the server stops issuing and returns 409 `exhausted`
so the page can say "all claimed" instead of handing someone a code that
another person already redeemed.

Config via env:
  GIFT_SITE    registration URL prefix (default https://iamstarchild.com)
  GIFT_PORT    listen port (default 9091)
  GIFT_PREFIX  only lines starting with this are treated as codes (default SC-),
               which lets you keep comments and notes inside codes.txt
"""
import json, os, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE = os.path.dirname(os.path.abspath(__file__))
CODES = os.path.join(BASE, "codes.txt")
STATE = os.path.join(BASE, "state.json")
LOCK = threading.Lock()

SITE = os.environ.get("GIFT_SITE", "https://iamstarchild.com")
PORT = int(os.environ.get("GIFT_PORT", "9091"))
PREFIX = os.environ.get("GIFT_PREFIX", "SC-")


def load_codes():
    """Read the pool, in file order. Duplicates are dropped so a copy-paste
    slip cannot hand the same code to two people."""
    if not os.path.exists(CODES):
        return []
    seen, out = set(), []
    with open(CODES) as f:
        for line in f:
            c = line.strip()
            if c.startswith(PREFIX) and c not in seen:
                seen.add(c)
                out.append(c)
    return out


def load_state():
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f)
    return {"counter": 0, "claims": {}}


def save_state(s):
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f, indent=1)
    os.replace(tmp, STATE)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        static = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/index.html": ("index.html", "text/html; charset=utf-8"),
            "/qr": ("qr.html", "text/html; charset=utf-8"),
            "/qr.html": ("qr.html", "text/html; charset=utf-8"),
            "/vendor/qrcode.min.js": ("vendor/qrcode.min.js",
                                      "application/javascript; charset=utf-8"),
        }
        if path in static:
            fname, ctype = static[path]
            with open(os.path.join(BASE, fname), "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/stats":
            with LOCK:
                s = load_state()
            self._json(200, {"total": len(load_codes()), "claimed": s["counter"]})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path.split("?")[0] != "/api/claim":
            return self._json(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n) or b"{}")
            cid = str(data.get("cid", ""))[:64]
        except Exception:
            return self._json(400, {"error": "bad request"})
        if not cid:
            return self._json(400, {"error": "missing cid"})
        with LOCK:
            s = load_state()
            codes = load_codes()
            if not codes:
                return self._json(500, {"error": "no codes"})
            if cid in s["claims"]:
                code = s["claims"][cid]
                repeat = True
            elif s["counter"] >= len(codes):
                # Pool exhausted. Never wrap around — a recycled code would
                # already be redeemed by its first owner and fail at signup.
                return self._json(409, {"error": "exhausted",
                                        "total": len(codes),
                                        "claimed": s["counter"]})
            else:
                code = codes[s["counter"]]
                s["claims"][cid] = code
                s["counter"] += 1
                save_state(s)
                repeat = False
        self._json(200, {"code": code, "repeat": repeat,
                         "url": f"{SITE}/?gift={code}"})


if __name__ == "__main__":
    print(f"gift-code-url listening on 0.0.0.0:{PORT}  site={SITE}")
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
