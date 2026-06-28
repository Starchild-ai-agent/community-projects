"use client";
import { useEffect, useRef } from "react";
import {
  ColorType,
  CrosshairMode,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";

export interface ChartCandle {
  time: number; // unix seconds
  open: number;
  high: number;
  low: number;
  close: number;
}

interface Props {
  pair: string;
  candles: ChartCandle[];
  livePrice: number | null;
  decimals: number;
}

export function PriceChart({ pair, candles, livePrice, decimals }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    let chart: IChartApi;
    try {
      chart = createChart(container, {
        layout: {
          background: { type: ColorType.Solid, color: "transparent" },
          textColor: "#64748b",
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
          attributionLogo: false,
        },
        grid: {
          vertLines: { color: "rgba(26,34,54,0.5)" },
          horzLines: { color: "rgba(26,34,54,0.5)" },
        },
        rightPriceScale: { borderColor: "rgba(26,34,54,0.8)", scaleMargins: { top: 0.1, bottom: 0.18 } },
        timeScale: { borderColor: "rgba(26,34,54,0.8)", timeVisible: true, secondsVisible: true, rightOffset: 6 },
        crosshair: {
          mode: CrosshairMode.Normal,
          vertLine: { color: "#2a344d", labelBackgroundColor: "#1a2236" },
          horzLine: { color: "#2a344d", labelBackgroundColor: "#1a2236" },
        },
        width: container.clientWidth || 360,
        height: container.clientHeight || 240,
      });
    } catch (e) {
      console.error("createChart failed:", e);
      return;
    }
    const series = chart.addCandlestickSeries({
      upColor: "#16c784", downColor: "#ea3943",
      borderUpColor: "#16c784", borderDownColor: "#ea3943",
      wickUpColor: "#16c784", wickDownColor: "#ea3943",
    });
    chartRef.current = chart;
    seriesRef.current = series;

    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) chart.applyOptions({ width, height });
      }
    });
    ro.observe(container);

    return () => {
      ro.disconnect();
      try { chart.remove(); } catch {}
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // When pair changes, reset data.
  useEffect(() => {
    if (!seriesRef.current) return;
    try {
      seriesRef.current.setData(
        candles.map(c => ({
          time: c.time as UTCTimestamp,
          open: c.open, high: c.high, low: c.low, close: c.close,
        }))
      );
      chartRef.current?.timeScale().fitContent();
    } catch (e) { console.error("setData:", e); }
  }, [pair]); // eslint-disable-line react-hooks/exhaustive-deps

  // Live update last candle from livePrice.
  useEffect(() => {
    if (!seriesRef.current || livePrice == null || candles.length === 0) return;
    const last = candles[candles.length - 1];
    try {
      seriesRef.current.update({
        time: last.time as UTCTimestamp,
        open: last.open,
        high: Math.max(last.high, livePrice),
        low: Math.min(last.low, livePrice),
        close: livePrice,
      });
    } catch {}
  }, [livePrice, candles]);

  return (
    <div className="relative h-[240px] w-full">
      <div className="absolute top-2 left-3 z-10 pointer-events-none">
        <span className="text-xs font-semibold text-slate-300">{pair}</span>
        {livePrice != null && (
          <span className="ml-2 font-mono text-xs text-slate-400">
            {livePrice.toFixed(decimals)}
          </span>
        )}
      </div>
      <div ref={containerRef} className="h-full w-full" />
    </div>
  );
}
