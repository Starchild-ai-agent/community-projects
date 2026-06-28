"use client";
import { useState } from "react";
import { useAccount, useWriteContract, useReadContract } from "wagmi";
import { parseUnits, formatUnits } from "viem";
import { TRADING_GAME_ADDRESS, TRADING_GAME_ABI } from "@/lib/contract.generated";
import { PAIRS, type Direction } from "@/lib/types";

const ERC20_ABI = [
  { inputs: [{ name: "spender", type: "address" }, { name: "amount", type: "uint256" }], name: "approve", outputs: [{ name: "", type: "bool" }], stateMutability: "nonpayable", type: "function" },
  { inputs: [{ name: "a", type: "address" }], name: "balanceOf", outputs: [{ name: "", type: "uint256" }], stateMutability: "view", type: "function" },
  { inputs: [{ name: "o", type: "address" }, { name: "a", type: "uint256" }], name: "allowance", outputs: [{ name: "", type: "uint256" }], stateMutability: "view", type: "function" },
] as const;

export function OpenTradeCard({ pair: initialPair = "SOL-PERP" }: { pair?: string } = {}) {
  const { address } = useAccount();
  const { writeContractAsync, isPending } = useWriteContract();
  const token = process.env.NEXT_PUBLIC_MARGIN_TOKEN_ADDRESS as `0x${string}` | undefined;
  const decimals = parseInt(process.env.NEXT_PUBLIC_MARGIN_TOKEN_DECIMALS || "18", 10);

  const [pair, setPair] = useState(initialPair);
  const [direction, setDirection] = useState<Direction>("UP");
  const [margin, setMargin] = useState("5");
  const [leverage] = useState(1000);
  const [tp, setTp] = useState("40");
  const [sl, setSl] = useState("40");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  const { data: allowance } = useReadContract({
    address: token,
    abi: ERC20_ABI,
    functionName: "allowance",
    args: [address || "0x0", TRADING_GAME_ADDRESS as `0x${string}`],
    query: { enabled: !!address && !!token },
  });

  async function handleApprove() {
    if (!token || !address) return;
    setBusy(true); setError(null);
    try {
      await writeContractAsync({
        address: token,
        abi: ERC20_ABI,
        functionName: "approve",
        args: [TRADING_GAME_ADDRESS as `0x${string}`, parseUnits("1000000", decimals)],
      });
      setOk("Approved");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function handleDeposit() {
    if (!token || !address) return;
    setBusy(true); setError(null);
    try {
      await writeContractAsync({
        address: TRADING_GAME_ADDRESS as `0x${string}`,
        abi: TRADING_GAME_ABI as any,
        functionName: "deposit",
        args: [parseUnits(margin || "0", decimals)],
      });
      setOk("Deposited");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function handleOpen() {
    if (!address) return;
    setBusy(true); setError(null); setOk(null);
    try {
      // 1. Ask backend for a signed open price
      const r = await fetch("/api/open-sign", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          pair, direction, margin: parseUnits(margin || "0", decimals).toString(),
          leverage, tpPct: parseFloat(tp) || 0, slPct: parseFloat(sl) || 0,
          userAddress: address,
        }),
      });
      const sig = await r.json();
      if (!r.ok) throw new Error(sig.error || "open-sign failed");

      // 2. Submit to contract
      const tx = await writeContractAsync({
        address: TRADING_GAME_ADDRESS as `0x${string}`,
        abi: TRADING_GAME_ABI as any,
        functionName: "openTrade",
        args: [
          sig.pairId,
          direction === "UP" ? 0 : 1,
          parseUnits(margin || "0", decimals),
          BigInt(leverage),
          BigInt(parseFloat(tp) || 0),
          BigInt(parseFloat(sl) || 0),
          BigInt(sig.priceScaled),
          BigInt(sig.timestamp),
          sig.signature as `0x${string}`,
        ],
      });
      setOk(`Trade opened. tx: ${tx.slice(0, 10)}…`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const needsApprove = allowance !== undefined && (allowance as bigint) < parseUnits(margin || "0", decimals);

  return (
    <div className="rounded-xl border border-line/60 bg-bg-800/60 p-4">
      <h2 className="text-sm font-semibold mb-3">Open Trade</h2>

      <label className="text-[11px] uppercase text-slate-500">Pair</label>
      <select value={pair} onChange={(e) => setPair(e.target.value)}
        className="w-full h-10 mb-3 mt-1 rounded-lg bg-bg-900/70 border border-line/60 px-3 text-sm">
        {PAIRS.map((p) => <option key={p.symbol} value={p.symbol}>{p.label}</option>)}
      </select>

      <div className="grid grid-cols-2 gap-2 mb-3">
        <button onClick={() => setDirection("UP")}
          className={`h-10 rounded-lg font-bold text-sm ${direction === "UP" ? "bg-up text-bg-900" : "bg-bg-700 text-slate-300"}`}>UP</button>
        <button onClick={() => setDirection("DOWN")}
          className={`h-10 rounded-lg font-bold text-sm ${direction === "DOWN" ? "bg-down text-white" : "bg-bg-700 text-slate-300"}`}>DOWN</button>
      </div>

      <label className="text-[11px] uppercase text-slate-500">Margin ({process.env.NEXT_PUBLIC_MARGIN_TOKEN_SYMBOL || "USDT"})</label>
      <input type="number" value={margin} onChange={(e) => setMargin(e.target.value)}
        className="w-full h-10 mb-3 mt-1 rounded-lg bg-bg-900/70 border border-line/60 px-3 font-mono text-sm" />

      <div className="grid grid-cols-2 gap-2 mb-3">
        <div>
          <label className="text-[11px] uppercase text-slate-500">TP % (max 40)</label>
          <input type="number" value={tp} onChange={(e) => setTp(String(Math.min(40, Math.max(0, parseFloat(e.target.value) || 0))))}
            className="w-full h-10 mt-1 rounded-lg bg-bg-900/70 border border-line/60 px-3 font-mono text-sm text-up" />
        </div>
        <div>
          <label className="text-[11px] uppercase text-slate-500">SL % (max 40)</label>
          <input type="number" value={sl} onChange={(e) => setSl(String(Math.min(40, Math.max(0, parseFloat(e.target.value) || 0))))}
            className="w-full h-10 mt-1 rounded-lg bg-bg-900/70 border border-line/60 px-3 font-mono text-sm text-down" />
        </div>
      </div>

      <div className="text-xs text-slate-500 mb-3">Leverage: <span className="text-warn font-semibold">{leverage}×</span> (fixed)</div>

      {error && <div className="mb-3 text-xs text-down bg-down/10 border border-down/30 rounded p-2">{error}</div>}
      {ok && <div className="mb-3 text-xs text-up bg-up/10 border border-up/30 rounded p-2">{ok}</div>}

      <div className="flex gap-2">
        {needsApprove && (
          <button onClick={handleApprove} disabled={busy || isPending || !address}
            className="flex-1 h-10 rounded-lg text-sm font-semibold border border-line-soft hover:bg-bg-700 disabled:opacity-40">
            Approve
          </button>
        )}
        <button onClick={handleDeposit} disabled={busy || isPending || !address}
          className="flex-1 h-10 rounded-lg text-sm font-semibold border border-line-soft hover:bg-bg-700 disabled:opacity-40">
          Deposit
        </button>
        <button onClick={handleOpen} disabled={busy || isPending || !address || needsApprove}
          className="flex-[2] h-10 rounded-lg text-sm font-bold bg-up text-bg-900 hover:bg-emerald-400 disabled:opacity-40">
          {busy ? "…" : "Open Trade"}
        </button>
      </div>
      {!address && <div className="mt-3 text-xs text-slate-500">Connect wallet to trade.</div>}
    </div>
  );
}
