"""HTTP compatibility shim.

Inside a Starchild container, routes through core.http_client (sc-proxy injects
credentials and bills per-caller). Anywhere else, falls back to plain requests —
all default endpoints used by QuoteSim (Hyperliquid info, Pyth Benchmarks,
Orderly public API) are free public APIs that need no keys.
"""
import os

CALLER = {"SC-CALLER-ID": "preview:quotesim"}

try:
    import sys
    _ws = os.environ.get("STARCHILD_WORKSPACE", "/data/workspace")
    if _ws not in sys.path:
        sys.path.insert(0, _ws)
    from core.http_client import proxied_get as _get, proxied_post as _post

    def http_get(url, **kw):
        kw.setdefault("headers", {}).update(CALLER)
        return _get(url, **kw)

    def http_post(url, **kw):
        kw.setdefault("headers", {}).update(CALLER)
        return _post(url, **kw)

    STARCHILD = True
except Exception:
    import requests

    def http_get(url, **kw):
        kw.pop("headers", None) if False else kw.setdefault("headers", {})
        return requests.get(url, **kw)

    def http_post(url, **kw):
        kw.setdefault("headers", {})
        return requests.post(url, **kw)

    STARCHILD = False
