"""
WOOFi Pro / Orderly Network API Client
Read-only by default. Order placement disabled until user approval.

Auth: ed25519 signature per request.
Headers: orderly-account-id, orderly-key, orderly-signature, orderly-timestamp
"""
import os
import time
import json
import base64
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    import base58
except ImportError as e:
    raise ImportError(
        "Missing deps. Run: pip install cryptography base58\n"
        f"Original error: {e}"
    )

BASE_URL = "https://api.orderly.org"  # mainnet


class OrderlyClient:
    def __init__(self, account_id=None, api_key=None, api_secret=None):
        self.account_id = account_id or os.environ.get("WOOFI_ACCOUNT_ID")
        # api_key is the public key (with ed25519: prefix), api_secret is private (base58)
        self.api_key = api_key or os.environ.get("WOOFI_API_KEY")
        self.api_secret = api_secret or os.environ.get("WOOFI_API_SECRET")
        self._priv_key = None

    @property
    def priv_key(self):
        if self._priv_key is None:
            secret = self.api_secret
            if secret.startswith("ed25519:"):
                secret = secret[len("ed25519:"):]
            raw = base58.b58decode(secret)
            self._priv_key = Ed25519PrivateKey.from_private_bytes(raw)
        return self._priv_key

    @property
    def public_key_header(self):
        """Return the orderly-key header value (with ed25519: prefix)."""
        if self.api_key and self.api_key.startswith("ed25519:"):
            return self.api_key
        return f"ed25519:{self.api_key}" if self.api_key else None

    def _sign(self, timestamp, method, path, body=""):
        message = f"{timestamp}{method}{path}{body}"
        sig = self.priv_key.sign(message.encode("utf-8"))
        return base64.b64encode(sig).decode("ascii")

    def _request(self, method, path, params=None, body=None, signed=False):
        method = method.upper()
        # build query string
        query = ""
        if params:
            from urllib.parse import urlencode
            query = "?" + urlencode(params)
        full_path = path + query
        url = BASE_URL + full_path

        body_str = ""
        if body is not None:
            body_str = json.dumps(body, separators=(",", ":"))

        headers = {"Content-Type": "application/json"}
        if signed:
            if not self.account_id:
                raise ValueError("WOOFI_ACCOUNT_ID not set — cannot sign requests")
            ts = str(int(time.time() * 1000))
            sig = self._sign(ts, method, full_path, body_str if method in ("POST", "PUT") else "")
            headers.update({
                "orderly-account-id": self.account_id,
                "orderly-key": self.public_key_header,
                "orderly-signature": sig,
                "orderly-timestamp": ts,
            })

        data = body_str.encode("utf-8") if body_str else None
        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            return {"success": False, "http_status": e.code, "error": err_body}
        except URLError as e:
            return {"success": False, "error": str(e)}

    # ---------- PUBLIC endpoints (no auth) ----------

    def get_system_status(self):
        return self._request("GET", "/v1/public/system_info")

    def get_all_markets(self):
        """List all perp markets with 24h stats + funding."""
        return self._request("GET", "/v1/public/futures")

    def get_market(self, symbol):
        """Single market info."""
        return self._request("GET", "/v1/public/futures", params={"symbol": symbol})

    def get_orderbook(self, symbol, depth=20):
        """Orderbook snapshot via public/query endpoint (no auth needed)."""
        body = {"type": "orderbook", "symbol": symbol, "depth": depth}
        req = Request(
            BASE_URL + "/v1/public/query",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_candles(self, symbol, interval="1h", limit=100):
        """OHLCV via public/query endpoint."""
        body = {
            "type": "candles",
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }
        req = Request(
            BASE_URL + "/v1/public/query",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_funding_rate_history(self, symbol, page_size=30):
        return self._request(
            "GET",
            "/v1/public/funding_rate_history",
            params={"symbol": symbol, "page_size": page_size},
        )

    # ---------- PRIVATE endpoints (signed) ----------

    def get_account_info(self):
        """Account state — requires account_id + signed request."""
        return self._request("GET", "/v1/client/info", signed=True)

    def get_balance(self):
        return self._request("GET", "/v1/client/holding", signed=True)

    def get_positions(self):
        return self._request("GET", "/v1/positions", signed=True)

    def get_orders(self, status="NEW", symbol=None):
        params = {"status": status}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/v1/orders", params=params, signed=True)

    def get_margin_modes(self):
        return self._request("GET", "/v1/client/margin_modes", signed=True)

    # ---------- ORDER placement ----------

    def create_order(self, symbol, order_type, side, order_price=None,
                     order_quantity=None, order_amount=None,
                     reduce_only=False, client_order_id=None):
        """
        POST /v1/order — place a limit or market order.
        order_type: LIMIT / MARKET / IOC / FOK / POST_ONLY / ASK / BID
        side: BUY / SELL
        """
        body = {
            "symbol": symbol,
            "order_type": order_type,
            "side": side,
            "reduce_only": reduce_only,
        }
        if order_price is not None:
            body["order_price"] = order_price
        if order_quantity is not None:
            body["order_quantity"] = order_quantity
        if order_amount is not None:
            body["order_amount"] = order_amount
        if client_order_id:
            body["client_order_id"] = client_order_id
        return self._request("POST", "/v1/order", body=body, signed=True)

    def create_stop_order(self, symbol, side, trigger_price, order_type="MARKET",
                          order_quantity=None, order_price=None, reduce_only=True,
                          client_order_id=None):
        """
        POST /v1/algo/order — place a stop-loss / take-profit order.
        algo_type: STOP (only type available).
        trigger_price_type: MARK_PRICE (only type available).
        """
        body = {
            "algo_type": "STOP",
            "symbol": symbol,
            "side": side,
            "type": order_type,  # LIMIT or MARKET
            "trigger_price": trigger_price,
            "trigger_price_type": "MARK_PRICE",
            "reduce_only": reduce_only,
        }
        if order_quantity is not None:
            body["quantity"] = order_quantity
        if order_price is not None:
            body["price"] = order_price
        if client_order_id:
            body["client_order_id"] = client_order_id
        return self._request("POST", "/v1/algo/order", body=body, signed=True)

    def cancel_order(self, order_id, symbol):
        """DELETE /v1/order — cancel a single order."""
        params = {"order_id": order_id, "symbol": symbol}
        return self._request("DELETE", "/v1/order", params=params, signed=True)

    def cancel_all_orders(self, symbol=None):
        """DELETE /v1/orders — cancel all open orders."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("DELETE", "/v1/orders", params=params, signed=True)

    def get_order(self, order_id):
        return self._request("GET", f"/v1/order/{order_id}", signed=True)


def quick_test():
    """Smoke test — public endpoints only."""
    c = OrderlyClient()  # no creds needed for public
    print("=== System status ===")
    print(c.get_system_status())
    print("\n=== BTC market ===")
    print(json.dumps(c.get_market("PERP_BTC_USDC"), indent=2))
    print("\n=== BTC orderbook (top 5) ===")
    ob = c.get_orderbook("PERP_BTC_USDC", depth=5)
    print(json.dumps(ob, indent=2)[:1500])


if __name__ == "__main__":
    quick_test()
