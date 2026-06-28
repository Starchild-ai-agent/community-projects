"use client";
import { useState } from "react";
import { useAccount, useWriteContract, useReadContract } from "wagmi";
import { formatUnits } from "viem";
import { TRADING_GAME_ADDRESS, TRADING_GAME_ABI } from "@/lib/contract.generated";

export function ActiveTradeCard() {
  const { address } = useAccount();
  const { writeContractAsync, isPending } = useWriteContract();
  const [tradeId, setTradeId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  // Read trade on-chain
  const { data: trade } = useReadContract({
    address: TRADING_GAME_ADDRESS as `0x${string}`,
    abi: TRADING_GAME_ABI as any,
    functionName: "getTrade",
    args: [BigInt(tradeId || "0")],
    query: { enabled: !!tradeId },
  });

  async function handleClose() {
    if (!address || !tradeId) return;
    setBusy(true); setError(null); setResult(null);
    try {
      const r = await fetch("/api/close-trade", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ tradeId: parseInt(tradeId), userAddress: address }),
      });
      const sig = await r.json();
      if (!r.ok) throw new Error(sig.error || "close-sign failed");

      const tx = await writeContractAsync({
        address: TRADING_GAME_ADDRESS as `0x${string}`,
        abi: TRADING_GAME_ABI as any,
        functionName: "closeTrade",
        args: [
          BigInt(tradeId),
          BigInt(sig.priceScaled),
          BigInt(sig.timestamp),
          sig.nonce as `0x${string}`,
          sig.signature as `0x${string}`,
        ],
      });
      setResult(`Closed. tx ${tx.slice(0,10)}… pnl ≈ ${sig.pnl.toFixed(4)}`);
    } catch (e) {
      setError((e as Error).message);
    } finally { setBusy(false); }
  }

  const t = trade as any;
  const isOpen = t && !t.closed && t.trader?.toLowerCase() === address?.toLowerCase();

  return (
    <div className="rounded-xl border border-line/60 bg-bg-800/60 p-4">
      <h2 className="text-sm font-semibold mb-3">Active Trade</h2>
      <label className="text-[11px] uppercase text-slate-500">Trade ID</label>
      <input type="number" value={tradeId} onChange={(e) => setTradeId(e.target.value)}
        placeholder="e.g. 1"
        className="w-full h-10 mb-3 mt-1 rounded-lg bg-bg-900/70 border border-line/60 px-3 font-mono text-sm" />

      {!t && <div className="text-xs text-slate-500">Enter a trade id to inspect.</div>}
      {t && (
        <div className="grid grid-cols-2 gap-2 text-xs mb-3">
          <Field label="Direction" value={Number(t.direction) === 0 ? "UP" : "DOWN"} />
          <Field label="Margin" value={formatUnits(t.margin, 18)} />
          <Field label="Leverage" value={`${t.leverage.toString()}×`} />
          <Field label="Open Price" value={(Number(t.openPrice) / 1e8).toFixed(4)} />
          <Field label="TP %" value={t.tpPct.toString()} />
          <Field label="SL %" value={t.slPct.toString()} />
          <Field label="Status" value={t.closed ? "closed" : "open"} />
          {t.closed && <Field label="PnL" value={formatUnits(t.pnl, 18)} />}
        </div>
      )}

      {error && <div className="mb-3 text-xs text-down bg-down/10 border border-down/30 rounded p-2">{error}</div>}
      {result && <div className="mb-3 text-xs text-up bg-up/10 border border-up/30 rounded p-2">{result}</div>}

      <button onClick={handleClose} disabled={busy || isPending || !isOpen}
        className="w-full h-10 rounded-lg text-sm font-bold bg-down text-white hover:bg-red-500 disabled:opacity-40">
        {busy ? "…" : "Close Trade"}
      </button>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="px-2 py-1.5 rounded-lg bg-bg-900/50 border border-line/40">
      <div className="text-[10px] uppercase text-slate-500">{label}</div>
      <div className="font-mono text-xs">{value}</div>
    </div>
  );
}
