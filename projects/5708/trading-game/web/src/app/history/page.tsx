"use client";
import { useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { useAccount } from "wagmi";
import Link from "next/link";
import type { TradeRow } from "@/lib/types";

export default function HistoryPage() {
  const { address } = useAccount();
  const [rows, setRows] = useState<TradeRow[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!address) return;
    setLoading(true);
    fetch(`/api/history?user=${address}`)
      .then((r) => r.json())
      .then((d) => setRows(d.trades || []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [address]);

  return (
    <div className="min-h-screen flex flex-col bg-bg-900">
      <Header />
      <main className="flex-1 p-3 sm:p-4 max-w-2xl mx-auto w-full">
        <nav className="flex gap-2 text-xs mb-3">
          <Link href="/" className="px-3 py-1.5 rounded-lg bg-bg-800 text-slate-400">Trade</Link>
          <Link href="/active" className="px-3 py-1.5 rounded-lg bg-bg-800 text-slate-400">Active</Link>
          <Link href="/history" className="px-3 py-1.5 rounded-lg bg-bg-700 text-slate-200">History</Link>
          <Link href="/admin" className="px-3 py-1.5 rounded-lg bg-bg-800 text-slate-400 ml-auto">Admin</Link>
        </nav>
        <h2 className="text-sm font-semibold mb-3">Trade History</h2>
        {!address && <div className="text-xs text-slate-500">Connect wallet.</div>}
        {loading && <div className="text-xs text-slate-500">Loading…</div>}
        {!loading && rows.length === 0 && <div className="text-xs text-slate-500">No trades yet.</div>}
        {rows.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-slate-500">
                <tr className="text-left">
                  <th className="py-2 pr-3">ID</th><th className="py-2 pr-3">Pair</th>
                  <th className="py-2 pr-3">Side</th><th className="py-2 pr-3 text-right">Open</th>
                  <th className="py-2 pr-3 text-right">Close</th><th className="py-2 pr-3 text-right">PnL</th>
                  <th className="py-2">Status</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {rows.map((r) => (
                  <tr key={r.id} className="border-t border-line/40">
                    <td className="py-2 pr-3">{r.trade_id ?? "—"}</td>
                    <td className="py-2 pr-3">{r.pair}</td>
                    <td className={`py-2 pr-3 ${r.direction === "UP" ? "text-up" : "text-down"}`}>{r.direction}</td>
                    <td className="py-2 pr-3 text-right">{r.open_price}</td>
                    <td className="py-2 pr-3 text-right">{r.close_price ?? "—"}</td>
                    <td className={`py-2 pr-3 text-right ${r.pnl != null && r.pnl >= 0 ? "text-up" : "text-down"}`}>
                      {r.pnl != null ? r.pnl.toFixed(4) : "—"}
                    </td>
                    <td className="py-2">{r.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
