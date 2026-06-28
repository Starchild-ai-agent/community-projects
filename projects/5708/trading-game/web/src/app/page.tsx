"use client";
import { useState } from "react";
import { Header } from "@/components/Header";
import { OpenTradeCard } from "@/components/OpenTradeCard";
import { ActiveTradeCard } from "@/components/ActiveTradeCard";
import { AutoCloseBanner } from "@/components/AutoCloseBanner";
import { PriceChart } from "@/components/PriceChart";
import Link from "next/link";
import { PAIRS } from "@/lib/types";

export default function Page() {
  const [symbol, setSymbol] = useState(PAIRS[0].symbol);
  return (
    <div className="min-h-screen flex flex-col bg-bg-900">
      <Header />
      <main className="flex-1 p-3 sm:p-4 max-w-md mx-auto w-full flex flex-col gap-3">
        <nav className="flex gap-2 text-xs">
          <Link href="/" className="px-3 py-1.5 rounded-lg bg-bg-700 text-slate-200">Trade</Link>
          <Link href="/active" className="px-3 py-1.5 rounded-lg bg-bg-800 text-slate-400">Active</Link>
          <Link href="/history" className="px-3 py-1.5 rounded-lg bg-bg-800 text-slate-400">History</Link>
          <Link href="/admin" className="px-3 py-1.5 rounded-lg bg-bg-800 text-slate-400 ml-auto">Admin</Link>
        </nav>
        <AutoCloseBanner />
        <div className="flex gap-2 text-xs">
          {PAIRS.map((p) => (
            <button key={p.symbol} onClick={() => setSymbol(p.symbol)}
              className={`px-3 py-1.5 rounded-lg ${symbol === p.symbol ? "bg-bg-700 text-slate-100" : "bg-bg-800 text-slate-400"}`}>
              {p.label}
            </button>
          ))}
        </div>
        <PriceChart symbol={symbol} height={200} />
        <OpenTradeCard pair={symbol} />
        <ActiveTradeCard />
      </main>
    </div>
  );
}