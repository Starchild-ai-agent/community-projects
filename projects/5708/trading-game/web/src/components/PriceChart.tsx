"use client";
import { useEffect, useRef, useState } from "react";

interface Props {
  symbol: string;
  priceProvider?: string;
  height?: number;
}

// Lightweight live price chart using SVG. No external chart library —
// renders close-price points as a line. Polls /api/pairs every 3s.
export function PriceChart({ symbol, height = 240 }: Props) {
  const [points, setPoints] = useState<{ t: number; p: number }[]>([]);
  const [latest, setLatest] = useState<number | null>(null);
  const [pairLabel, setPairLabel] = useState(symbol);
  const wsRef = useRef<number | null>(null);

  useEffect(() => {
    setPoints([]);
    const tick = async () => {
      try {
        const r = await fetch(`/api/pairs`);
        if (!r.ok) return;
        const d = await r.json();
        const p = (d.pairs || []).find((x: any) => x.symbol === symbol);
        if (!p || p.price == null) return;
        setPairLabel(p.label || symbol);
        const t = Date.now();
        setLatest(p.price);
        setPoints((prev) => {
          const next = [...prev, { t, p: p.price }];
          return next.slice(-120);
        });
      } catch { /* ignore */ }
    };
    tick();
    const id = window.setInterval(tick, 3000);
    return () => window.clearInterval(id);
  }, [symbol]);

  const w = 320;
  const h = height;
  const padTop = 10, padBot = 18;
  const padX = 4;
  const innerW = w - padX * 2;
  const innerH = h - padTop - padBot;

  let path = "";
  let min = Infinity, max = -Infinity;
  for (const pt of points) { if (pt.p < min) min = pt.p; if (pt.p > max) max = pt.p; }
  if (points.length < 2 || min === max) { min = (latest || 0) * 0.999; max = (latest || 1) * 1.001; }
  const range = max - min || 1;
  points.forEach((pt, i) => {
    const x = padX + (i / Math.max(points.length - 1, 1)) * innerW;
    const y = padTop + (1 - (pt.p - min) / range) * innerH;
    path += i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`;
  });

  const changePct = points.length >= 2
    ? ((points[points.length - 1].p - points[0].p) / points[0].p) * 100
    : 0;
  const up = changePct >= 0;
  const stroke = up ? "#16c784" : "#ea3943";

  return (
    <div className="rounded-xl border border-line/60 bg-bg-800/60 p-3">
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="text-sm font-semibold">{pairLabel}</div>
          <div className="text-[10px] text-slate-500">3s · live (sim)</div>
        </div>
        <div className="text-right">
          <div className={`font-mono text-base font-bold ${up ? "text-up" : "text-down"}`}>
            {latest != null ? latest.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 4 }) : "—"}
          </div>
          <div className={`text-[10px] font-mono ${up ? "text-up" : "text-down"}`}>
            {up ? "+" : ""}{changePct.toFixed(3)}%
          </div>
        </div>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" preserveAspectRatio="none" style={{ height }}>
        <defs>
          <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={stroke} stopOpacity="0.3" />
            <stop offset="100%" stopColor={stroke} stopOpacity="0" />
          </linearGradient>
        </defs>
        {/* grid */}
        {[0.25, 0.5, 0.75].map((r) => (
          <line key={r} x1={padX} y1={padTop + r * innerH} x2={w - padX} y2={padTop + r * innerH} stroke="#1a2236" strokeWidth="0.5" />
        ))}
        {points.length > 1 && (
          <>
            <path d={`${path} L ${padX + innerW} ${padTop + innerH} L ${padX} ${padTop + innerH} Z`} fill="url(#g)" />
            <path d={path} fill="none" stroke={stroke} strokeWidth="1.5" />
          </>
        )}
        {points.length > 0 && (
          <circle
            cx={padX + innerW}
            cy={padTop + (1 - (points[points.length - 1].p - min) / range) * innerH}
            r="2"
            fill={stroke}
          />
        )}
      </svg>
    </div>
  );
}