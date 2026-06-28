"use client";
import { useEffect, useRef, useState } from "react";
import { PriceChart, type ChartCandle } from "@/components/chart/PriceChart";
import { PAIRS } from "@/lib/types";

interface Props {
  pair: string;
  onPrice?: (price: number) => void;
}

/**
 * Live price chart that polls /api/price every 1s and builds 5s candles
 * client-side from the stream. Seeds with a flat history so the chart
 * isn't empty on first paint.
 */
export function LiveChart({ pair, onPrice }: Props) {
  const cfg = PAIRS.find(p => p.symbol === pair) || PAIRS[0];
  const [candles, setCandles] = useState<ChartCandle[]>([]);
  const [livePrice, setLivePrice] = useState<number | null>(null);
  const candleStartRef = useRef<number>(0);
  const openRef = useRef<number>(0);
  const highRef = useRef<number>(0);
  const lowRef = useRef<number>(Infinity);
  const seededRef = useRef<string>("");

  // Seed flat history on pair change
  useEffect(() => {
    if (seededRef.current === pair) return;
    seededRef.current = pair;
    const now = Math.floor(Date.now() / 1000);
    const seed: ChartCandle[] = [];
    for (let i = 60; i > 0; i--) {
      seed.push({ time: now - i * 5, open: 0, high: 0, low: 0, close: 0 });
    }
    setCandles(seed);
    candleStartRef.current = now;
    openRef.current = 0; highRef.current = 0; lowRef.current = Infinity;
  }, [pair]);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const r = await fetch(`/api/price?pair=${encodeURIComponent(pair)}`);
        if (!r.ok) return;
        const j = await r.json();
        if (cancelled || !j.price) return;
        const price = j.price as number;
        setLivePrice(price);
        onPrice?.(price);

        setCandles(prev => {
          const now = Math.floor(Date.now() / 1000);
          // start a new candle every 5s
          if (candleStartRef.current === 0 || now - candleStartRef.current >= 5) {
            candleStartRef.current = now;
            openRef.current = price;
            highRef.current = price;
            lowRef.current = price;
            const next = [...prev, { time: now, open: price, high: price, low: price, close: price }];
            // keep last 120 candles
            if (next.length > 120) next.shift();
            return next;
          }
          // update current candle
          highRef.current = Math.max(highRef.current, price);
          lowRef.current = Math.min(lowRef.current, price);
          const last = next[next.length - 1] || { time: now, open: price, high: price, low: price, close: price };
          if (last.open === 0) { last.open = price; last.high = price; last.low = price; }
          last.high = Math.max(last.high, price);
          last.low = Math.min(last.low, price);
          last.close = price;
          return [...next];
        });
      } catch {}
    }
    poll();
    const id = setInterval(poll, 1000);
    return () => { cancelled = true; clearInterval(id); };
  }, [pair, onPrice]);

  return (
    <div className="rounded-xl border border-line/60 bg-bg-800/40 overflow-hidden">
      <PriceChart pair={pair} candles={candles} livePrice={livePrice} decimals={cfg.decimals} />
    </div>
  );
}
