"""
Derivatives data: funding rates, open interest, liquidations.

Provider strategy:
- Coinglass (recommended): wider cross-exchange derivatives context
- Exchange fallback (ccxt): keeps analyzer running without Coinglass key

ccxt returns funding rates as fractions: 0.0001 = 0.01% per interval.
On Binance, +0.01%/8h is the NEUTRAL baseline — thresholds below are
set relative to that, not to zero.
"""

import time
from collections import deque

try:
    import ccxt.pro as ccxtpro
except Exception:
    # Fallback for environments without ccxt.pro installed.
    import ccxt.async_support as ccxtpro
import httpx

from . import config

# Funding rate thresholds (fractions per 8h interval)
FUNDING_EXTREME = 0.0005   # 0.05%/8h — heavily crowded
FUNDING_MODERATE = 0.0002  # 0.02%/8h — leaning crowded
FUNDING_NEG_MODERATE = -0.0001  # any negative funding is already notable

# OI change is measured against the oldest sample in this window
OI_WINDOW_SECONDS = 3600
OI_CHANGE_NOTABLE_PCT = 2.0
PRICE_CHANGE_NOTABLE_PCT = 0.5


class DerivativesData:
    def __init__(self):
        self._exchange = None
        if config.DERIV_PROVIDER in {"auto", "exchange"}:
            exchange_class = getattr(ccxtpro, config.EXCHANGE)
            self._exchange = exchange_class({"enableRateLimit": True})

        self._http = httpx.AsyncClient(timeout=15)
        self._cache: dict[str, dict] = {}  # symbol → data
        self._last_fetch: dict[str, float] = {}
        self._fetch_interval = 60  # poll every 60s (REST, not WS)
        # symbol → deque of (timestamp, open_interest, price) samples
        self._history: dict[str, deque] = {}

    @staticmethod
    def _swap_symbol(symbol: str) -> str:
        """Map a spot symbol to its linear perpetual (BTC/USDT → BTC/USDT:USDT)."""
        if ":" in symbol:
            return symbol
        quote = symbol.split("/")[1]
        return f"{symbol}:{quote}"

    @staticmethod
    def _base_symbol(symbol: str) -> str:
        return symbol.split("/")[0].upper()

    async def get(self, symbol: str, price: float = None) -> dict:
        """Get derivatives data for a symbol. Cached for 60s."""
        now = time.time()
        if symbol in self._cache:
            if now - self._last_fetch.get(symbol, 0) < self._fetch_interval:
                return self._cache[symbol]

        data = await self._fetch(symbol, price)
        self._cache[symbol] = data
        self._last_fetch[symbol] = now
        return data

    async def _fetch(self, symbol: str, price: float = None) -> dict:
        # Provider order:
        # - auto: Coinglass (if key) -> exchange
        # - coinglass: Coinglass only
        # - exchange: exchange only
        provider = config.DERIV_PROVIDER

        if provider == "coinglass":
            result = await self._fetch_coinglass(symbol, price)
            if result:
                result["provider"] = "coinglass"
                return result
            return self._empty_result("coinglass")

        if provider == "exchange":
            result = await self._fetch_exchange(symbol, price)
            result["provider"] = "exchange"
            return result

        # auto
        if config.COINGLASS_API_KEY:
            result = await self._fetch_coinglass(symbol, price)
            if result:
                result["provider"] = "coinglass"
                return result

        result = await self._fetch_exchange(symbol, price)
        result["provider"] = "exchange"
        return result

    def _empty_result(self, provider: str) -> dict:
        return {
            "funding_rate": None,
            "funding_rate_signal": "neutral",
            "open_interest": None,
            "open_interest_change_pct": None,
            "oi_signal": "neutral",
            "provider": provider,
        }

    async def _fetch_coinglass(self, symbol: str, price: float = None) -> dict | None:
        if not config.COINGLASS_API_KEY:
            return None

        base = self._base_symbol(symbol)
        headers = {
            "CG-API-KEY": config.COINGLASS_API_KEY,
            "accept": "application/json",
        }

        out = self._empty_result("coinglass")

        # Funding (aggregated)
        try:
            # v4 docs show this under futures funding history/candles
            # Use a short window and latest point.
            fr_url = f"{config.COINGLASS_BASE_URL}/api/futures/fundingRate/ohlc-history"
            fr_resp = await self._http.get(
                fr_url,
                params={"symbol": base, "interval": "1h", "limit": 1},
                headers=headers,
            )
            fr_resp.raise_for_status()
            fr_data = fr_resp.json()

            latest_rate = self._extract_latest_num(fr_data, keys=("close", "c", "fundingRate", "value"))
            if latest_rate is not None:
                # Funding is expected in fraction form in most feeds
                out["funding_rate"] = round(float(latest_rate) * 100, 4)
                rate = float(latest_rate)
                if rate >= FUNDING_EXTREME:
                    out["funding_rate_signal"] = "extremely_long"
                elif rate >= FUNDING_MODERATE:
                    out["funding_rate_signal"] = "moderately_long"
                elif rate <= -FUNDING_EXTREME:
                    out["funding_rate_signal"] = "extremely_short"
                elif rate <= FUNDING_NEG_MODERATE:
                    out["funding_rate_signal"] = "moderately_short"
                else:
                    out["funding_rate_signal"] = "neutral"
        except Exception as e:
            print(f"[DERIV] Coinglass funding error {symbol}: {e}")

        # Open interest (aggregated)
        try:
            oi_url = f"{config.COINGLASS_BASE_URL}/api/futures/openInterest/aggregated-history"
            oi_resp = await self._http.get(
                oi_url,
                params={"symbol": base, "interval": "1h", "limit": 2},
                headers=headers,
            )
            oi_resp.raise_for_status()
            oi_data = oi_resp.json()

            latest_oi = self._extract_latest_num(oi_data, keys=("openInterest", "oi", "close", "c", "value"))
            if latest_oi is not None:
                out["open_interest"] = float(latest_oi)
                self._track_oi(symbol, float(latest_oi), price, out)
        except Exception as e:
            print(f"[DERIV] Coinglass OI error {symbol}: {e}")

        if out["funding_rate"] is None and out["open_interest"] is None:
            return None
        return out

    @staticmethod
    def _extract_latest_num(payload: dict, keys: tuple[str, ...]) -> float | None:
        """
        Lenient JSON parser for endpoint shape differences:
        - {data:[{...}, ...]}
        - {data:{list:[...]}}
        - {result:[...]}
        - direct list payload
        """
        candidates = []

        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                candidates = data
            elif isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, list) and v:
                        candidates = v
                        break
            if not candidates:
                result = payload.get("result")
                if isinstance(result, list):
                    candidates = result

        if not candidates and isinstance(payload, list):
            candidates = payload

        if not candidates:
            return None

        last = candidates[-1]
        if not isinstance(last, dict):
            return None

        for k in keys:
            v = last.get(k)
            if v is None:
                continue
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
        return None

    async def _fetch_exchange(self, symbol: str, price: float = None) -> dict:
        result = self._empty_result("exchange")
        if not self._exchange:
            return result

        swap = self._swap_symbol(symbol)

        try:
            # Funding rate (perpetuals only — derive the swap symbol)
            funding = await self._exchange.fetch_funding_rate(swap)
            if funding:
                rate = funding.get("fundingRate")
                if rate is not None:
                    result["funding_rate"] = round(rate * 100, 4)  # as percentage
                    if rate >= FUNDING_EXTREME:
                        result["funding_rate_signal"] = "extremely_long"
                    elif rate >= FUNDING_MODERATE:
                        result["funding_rate_signal"] = "moderately_long"
                    elif rate <= -FUNDING_EXTREME:
                        result["funding_rate_signal"] = "extremely_short"
                    elif rate <= FUNDING_NEG_MODERATE:
                        result["funding_rate_signal"] = "moderately_short"
                    else:
                        result["funding_rate_signal"] = "neutral"
        except Exception as e:
            err = str(e).lower()
            if "does not have" not in err and "contract" not in err:
                print(f"[DERIV] Funding rate error {symbol}: {e}")

        try:
            # Open interest
            oi_data = await self._exchange.fetch_open_interest(swap)
            if oi_data:
                oi_value = oi_data.get("openInterestValue") or oi_data.get("openInterestAmount")
                if oi_value:
                    result["open_interest"] = oi_value
                    self._track_oi(symbol, oi_value, price, result)
        except Exception as e:
            err = str(e).lower()
            if "does not have" not in err and "contract" not in err:
                print(f"[DERIV] OI error {symbol}: {e}")

        return result

    def _track_oi(self, symbol: str, oi_value: float, price: float, result: dict):
        """Sample OI (and price) over time and classify the OI/price combination."""
        now = time.time()
        hist = self._history.setdefault(symbol, deque(maxlen=240))
        hist.append((now, oi_value, price))

        # Oldest sample inside the window, requiring at least half a window
        # of history so early readings don't produce noise
        baseline = None
        for ts, oi, px in hist:
            if now - ts <= OI_WINDOW_SECONDS:
                baseline = (ts, oi, px)
                break
        if not baseline or now - baseline[0] < OI_WINDOW_SECONDS / 2:
            return

        _, oi_then, px_then = baseline
        if not oi_then:
            return
        oi_chg = (oi_value - oi_then) / oi_then * 100
        result["open_interest_change_pct"] = round(oi_chg, 2)

        px_chg = None
        if price and px_then:
            px_chg = (price - px_then) / px_then * 100

        if oi_chg > OI_CHANGE_NOTABLE_PCT:
            if px_chg is not None and px_chg > PRICE_CHANGE_NOTABLE_PCT:
                result["oi_signal"] = "longs_adding"       # new money chasing the move
            elif px_chg is not None and px_chg < -PRICE_CHANGE_NOTABLE_PCT:
                result["oi_signal"] = "shorts_adding"      # shorts piling in, squeeze fuel
            else:
                result["oi_signal"] = "oi_rising"
        elif oi_chg < -OI_CHANGE_NOTABLE_PCT:
            result["oi_signal"] = "positions_unwinding"     # trend exhaustion

    def format_for_llm(self, data: dict) -> str:
        """Format derivatives data for LLM context."""
        if not data or data.get("funding_rate") is None:
            return "Derivatives data unavailable (no perpetual market or fetch failed)."

        lines = []
        provider = data.get("provider", "unknown")
        fr = data["funding_rate"]
        signal = data["funding_rate_signal"]
        lines.append(f"**Derivatives Source:** {provider}")
        lines.append(f"**Funding Rate:** {fr:.4f}% per 8h ({signal}; +0.0100% is the neutral baseline)")

        if signal == "extremely_long":
            lines.append("  → Crowded longs — elevated correction/squeeze risk")
        elif signal == "extremely_short":
            lines.append("  → Crowded shorts — elevated short-squeeze risk")
        elif signal == "moderately_long":
            lines.append("  → Longs paying shorts — mild bullish positioning")
        elif signal == "moderately_short":
            lines.append("  → Shorts paying longs — mild bearish positioning")

        oi = data.get("open_interest")
        if oi:
            oi_line = f"**Open Interest:** ${oi:,.0f}"
            oi_chg = data.get("open_interest_change_pct")
            if oi_chg is not None:
                oi_line += f" ({oi_chg:+.2f}% over last hour)"
            lines.append(oi_line)

        oi_signal = data.get("oi_signal", "neutral")
        if oi_signal == "longs_adding":
            lines.append("  → OI and price rising together — new longs, trend confirmation")
        elif oi_signal == "shorts_adding":
            lines.append("  → OI rising while price falls — shorts piling in, squeeze potential")
        elif oi_signal == "oi_rising":
            lines.append("  → OI rising without a clear price move — positioning building")
        elif oi_signal == "positions_unwinding":
            lines.append("  → OI falling — positions closing, possible trend exhaustion")

        return "\n".join(lines)

    async def close(self):
        if self._exchange:
            await self._exchange.close()
        await self._http.aclose()
