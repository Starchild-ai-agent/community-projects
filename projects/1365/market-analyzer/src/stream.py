import asyncio
import random
import time
from collections import deque
from typing import Callable

try:
    import ccxt.pro as ccxtpro
except Exception:
    # Fallback for environments without ccxt.pro installed.
    # Keeps import-time compatibility for tests that don't require WS streaming.
    import ccxt.async_support as ccxtpro

from . import config


class CandleBuffer:
    def __init__(self):
        self.timeframes = {
            tf: deque(maxlen=config.BUFFER_SIZE)
            for tf in config.TIMEFRAMES
        }
        # Track last seen timestamp per timeframe to detect new candle closes
        self._last_ts = {tf: 0 for tf in config.TIMEFRAMES}

    def push(self, timeframe: str, candle: dict) -> bool:
        """Push a candle. Returns True if this is a NEW closed candle."""
        ts = candle["timestamp"]
        buf = self.timeframes[timeframe]

        if ts > self._last_ts[timeframe]:
            # New candle timestamp — the previous candle just closed
            self._last_ts[timeframe] = ts
            buf.append(candle)
            return True

        # Same timestamp — candle still forming, update in place
        if buf:
            buf[-1] = candle
        else:
            buf.append(candle)
        return False


class MarketStream:
    def __init__(self):
        exchange_class = getattr(ccxtpro, config.EXCHANGE)
        self.exchange = exchange_class({"enableRateLimit": True})
        self.buffers = {s: CandleBuffer() for s in config.SYMBOLS}
        self._callbacks: list[Callable] = []

    def on_candle(self, callback: Callable):
        self._callbacks.append(callback)

    async def start(self):
        # Stagger subscriptions: Binance closes the connection with 1008
        # (policy violation) if it receives more than ~5 inbound messages
        # per second, and a simultaneous burst of SUBSCRIBEs exceeds that.
        tasks = []
        for symbol in config.SYMBOLS:
            for tf in config.TIMEFRAMES:
                tasks.append(asyncio.create_task(self._watch(symbol, tf)))
                await asyncio.sleep(0.3)
        await asyncio.gather(*tasks)

    async def _prefill(self):
        """Fetch recent historical candles via REST to warm up buffers."""
        print("[STREAM] Pre-filling buffers with historical data...")
        for symbol in config.SYMBOLS:
            for tf in config.TIMEFRAMES:
                try:
                    ohlcv = await self.exchange.fetch_ohlcv(
                        symbol, tf, limit=config.BUFFER_SIZE
                    )
                    buf = self.buffers[symbol]
                    for raw in ohlcv:
                        candle = {
                            "timestamp": raw[0],
                            "open": raw[1],
                            "high": raw[2],
                            "low": raw[3],
                            "close": raw[4],
                            "volume": raw[5],
                        }
                        buf.timeframes[tf].append(candle)
                        buf._last_ts[tf] = raw[0]
                    count = len(buf.timeframes[tf])
                    print(f"[STREAM] {symbol} {tf}: {count} candles loaded")
                except Exception as e:
                    print(f"[STREAM] Prefill error {symbol} {tf}: {e}")
        print("[STREAM] Pre-fill complete — starting live stream")

    async def _watch(self, symbol: str, timeframe: str):
        # _stream_loop only returns by raising, so reset backoff based on how
        # long the connection survived rather than on a normal return.
        backoff = 1
        while True:
            started = time.monotonic()
            try:
                await self._stream_loop(symbol, timeframe)
            except Exception as e:
                kind = "Network error" if isinstance(e, ccxtpro.NetworkError) else "Error"
                print(f"[STREAM] {kind} {symbol} {timeframe}: {e}")
                if time.monotonic() - started > 60:
                    backoff = 1  # connection was stable for a while
                # Jitter so all watchers don't resubscribe in the same burst
                # and trip the rate limit again
                await asyncio.sleep(min(backoff, 30) + random.uniform(0, 3))
                backoff *= 2

    async def _stream_loop(self, symbol: str, timeframe: str):
        while True:
            ohlcv_list = await self.exchange.watch_ohlcv(symbol, timeframe)
            buf = self.buffers[symbol]

            for raw in ohlcv_list:
                candle = {
                    "timestamp": raw[0],
                    "open": raw[1],
                    "high": raw[2],
                    "low": raw[3],
                    "close": raw[4],
                    "volume": raw[5],
                }
                is_new = buf.push(timeframe, candle)

                if is_new:
                    for cb in self._callbacks:
                        asyncio.create_task(
                            cb(symbol, timeframe, buf)
                        )

    async def close(self):
        await self.exchange.close()
