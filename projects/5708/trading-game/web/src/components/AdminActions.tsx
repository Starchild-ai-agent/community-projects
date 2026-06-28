"use client";
import { useState } from "react";
import { useWriteContract, useReadContract } from "wagmi";
import { TRADING_GAME_ADDRESS, TRADING_GAME_ABI } from "@/lib/contract.generated";

export function PauseToggle() {
  const { writeContractAsync, isPending } = useWriteContract();
  const { data: paused, refetch } = useReadContract({
    address: TRADING_GAME_ADDRESS as `0x${string}`,
    abi: TRADING_GAME_ABI as any,
    functionName: "paused",
  });
  const [err, setErr] = useState<string | null>(null);
  async function toggle() {
    setErr(null);
    try {
      await writeContractAsync({
        address: TRADING_GAME_ADDRESS as `0x${string}`,
        abi: TRADING_GAME_ABI as any,
        functionName: paused ? "unpause" : "pause",
      });
      await refetch();
    } catch (e) { setErr((e as Error).message); }
  }
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <div>
        <div className="text-sm font-semibold">Trading paused</div>
        <div className="text-[10px] text-slate-500">Halts all open/close/deposit</div>
      </div>
      <div className="flex items-center gap-2">
        <span className={`text-xs font-mono ${paused ? "text-down" : "text-up"}`}>{paused ? "PAUSED" : "ACTIVE"}</span>
        <button onClick={toggle} disabled={isPending}
          className={`h-8 px-3 rounded-lg text-xs font-semibold ${paused ? "bg-up text-bg-900" : "bg-down text-white"} disabled:opacity-40`}>
          {isPending ? "…" : paused ? "Unpause" : "Pause"}
        </button>
      </div>
      {err && <div className="text-[10px] text-down col-span-2">{err}</div>}
    </div>
  );
}

export function SetRiskParams() {
  const { writeContractAsync, isPending } = useWriteContract();
  const { data: profit } = useReadContract({ address: TRADING_GAME_ADDRESS as `0x${string}`, abi: TRADING_GAME_ABI as any, functionName: "maxProfitPct" });
  const { data: loss } = useReadContract({ address: TRADING_GAME_ADDRESS as `0x${string}`, abi: TRADING_GAME_ABI as any, functionName: "maxLossPct" });
  const { data: fee } = useReadContract({ address: TRADING_GAME_ADDRESS as `0x${string}`, abi: TRADING_GAME_ABI as any, functionName: "platformFeePct" });
  const [p, setP] = useState(""); const [l, setL] = useState(""); const [f, setF] = useState("");
  const [err, setErr] = useState<string | null>(null); const [ok, setOk] = useState<string | null>(null);
  async function submit() {
    setErr(null); setOk(null);
    try {
      await writeContractAsync({
        address: TRADING_GAME_ADDRESS as `0x${string}`, abi: TRADING_GAME_ABI as any,
        functionName: "adminSetRiskParams",
        args: [BigInt(Math.floor(parseFloat(p)||0)), BigInt(Math.floor(parseFloat(l)||0)), BigInt(Math.floor(parseFloat(f)||0))],
      });
      setOk("Risk params updated");
    } catch (e) { setErr((e as Error).message); }
  }
  return (
    <div className="py-2 space-y-2">
      <div className="text-sm font-semibold">Risk params</div>
      <div className="text-[10px] text-slate-500">Current: profit {(profit as bigint|undefined)?.toString()||"—"}% · loss {(loss as bigint|undefined)?.toString()||"—"}% · fee {(fee as bigint|undefined)?.toString()||"—"}%</div>
      <div className="grid grid-cols-3 gap-2">
        <input type="number" placeholder="Profit %" value={p} onChange={(e)=>setP(e.target.value)} className="h-8 rounded bg-bg-900/70 border border-line/60 px-2 text-xs font-mono text-up" />
        <input type="number" placeholder="Loss %" value={l} onChange={(e)=>setL(e.target.value)} className="h-8 rounded bg-bg-900/70 border border-line/60 px-2 text-xs font-mono text-down" />
        <input type="number" placeholder="Fee %" value={f} onChange={(e)=>setF(e.target.value)} className="h-8 rounded bg-bg-900/70 border border-line/60 px-2 text-xs font-mono" />
      </div>
      <button onClick={submit} disabled={isPending} className="h-8 px-3 rounded-lg text-xs font-semibold bg-up text-bg-900 disabled:opacity-40">{isPending ? "…" : "Update"}</button>
      {err && <div className="text-[10px] text-down">{err}</div>}
      {ok && <div className="text-[10px] text-up">{ok}</div>}
    </div>
  );
}

export function SetOracleSigner() {
  const { writeContractAsync, isPending } = useWriteContract();
  const { data: current } = useReadContract({ address: TRADING_GAME_ADDRESS as `0x${string}`, abi: TRADING_GAME_ABI as any, functionName: "oracleSigner" });
  const [addr, setAddr] = useState(""); const [err, setErr] = useState<string|null>(null); const [ok, setOk] = useState<string|null>(null);
  async function submit() {
    setErr(null); setOk(null);
    if (!addr.startsWith("0x") || addr.length !== 42) { setErr("bad address"); return; }
    try {
      await writeContractAsync({ address: TRADING_GAME_ADDRESS as `0x${string}`, abi: TRADING_GAME_ABI as any, functionName: "adminSetOracleSigner", args: [addr as `0x${string}`] });
      setOk("Oracle signer updated"); setAddr("");
    } catch (e) { setErr((e as Error).message); }
  }
  return (
    <div className="py-2 space-y-2">
      <div className="text-sm font-semibold">Oracle signer</div>
      <div className="text-[10px] text-slate-500 font-mono break-all">Current: {current as string | undefined}</div>
      <input value={addr} onChange={(e)=>setAddr(e.target.value)} placeholder="0x…" className="w-full h-8 rounded bg-bg-900/70 border border-line/60 px-2 text-xs font-mono" />
      <button onClick={submit} disabled={isPending} className="h-8 px-3 rounded-lg text-xs font-semibold bg-up text-bg-900 disabled:opacity-40">{isPending ? "…" : "Set signer"}</button>
      {err && <div className="text-[10px] text-down">{err}</div>}
      {ok && <div className="text-[10px] text-up">{ok}</div>}
    </div>
  );
}

export function SetPairForm() {
  const { writeContractAsync, isPending } = useWriteContract();
  const [symbol, setSymbol] = useState("SOL-PERP"); const [supported, setSupported] = useState(true); const [maxLev, setMaxLev] = useState("1000");
  const [err, setErr] = useState<string|null>(null); const [ok, setOk] = useState<string|null>(null);
  async function submit() {
    setErr(null); setOk(null);
    try {
      const { keccak256, toUtf8Bytes } = await import("viem");
      const id = keccak256(toUtf8Bytes(symbol));
      await writeContractAsync({ address: TRADING_GAME_ADDRESS as `0x${string}`, abi: TRADING_GAME_ABI as any, functionName: "adminSetPair", args: [id, supported, BigInt(parseInt(maxLev)||0)] });
      setOk(`Pair ${symbol} ${supported ? "enabled" : "disabled"} @ ${maxLev}×`);
    } catch (e) { setErr((e as Error).message); }
  }
  return (
    <div className="py-2 space-y-2">
      <div className="text-sm font-semibold">Pair config</div>
      <input value={symbol} onChange={(e)=>setSymbol(e.target.value)} placeholder="SOL-PERP" className="w-full h-8 rounded bg-bg-900/70 border border-line/60 px-2 text-xs font-mono" />
      <div className="flex gap-2">
        <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={supported} onChange={(e)=>setSupported(e.target.checked)} /> Supported</label>
        <input type="number" value={maxLev} onChange={(e)=>setMaxLev(e.target.value)} placeholder="Max lev" className="h-8 w-24 rounded bg-bg-900/70 border border-line/60 px-2 text-xs font-mono" />
        <button onClick={submit} disabled={isPending} className="h-8 px-3 rounded-lg text-xs font-semibold bg-up text-bg-900 disabled:opacity-40">{isPending ? "…" : "Set pair"}</button>
      </div>
      {err && <div className="text-[10px] text-down">{err}</div>}
      {ok && <div className="text-[10px] text-up">{ok}</div>}
    </div>
  );
}

export function SetFeeRecipient() {
  const { writeContractAsync, isPending } = useWriteContract();
  const [addr, setAddr] = useState(""); const [err, setErr] = useState<string|null>(null); const [ok, setOk] = useState<string|null>(null);
  async function submit() {
    setErr(null); setOk(null);
    if (!addr.startsWith("0x") || addr.length !== 42) { setErr("bad address"); return; }
    try {
      await writeContractAsync({ address: TRADING_GAME_ADDRESS as `0x${string}`, abi: TRADING_GAME_ABI as any, functionName: "adminSetFeeRecipient", args: [addr as `0x${string}`] });
      setOk("Fee recipient updated"); setAddr("");
    } catch (e) { setErr((e as Error).message); }
  }
  return (
    <div className="py-2 space-y-2">
      <div className="text-sm font-semibold">Fee recipient</div>
      <input value={addr} onChange={(e)=>setAddr(e.target.value)} placeholder="0x…" className="w-full h-8 rounded bg-bg-900/70 border border-line/60 px-2 text-xs font-mono" />
      <button onClick={submit} disabled={isPending} className="h-8 px-3 rounded-lg text-xs font-semibold bg-up text-bg-900 disabled:opacity-40">{isPending ? "…" : "Set recipient"}</button>
      {err && <div className="text-[10px] text-down">{err}</div>}
      {ok && <div className="text-[10px] text-up">{ok}</div>}
    </div>
  );
}

export function SetOneTradePerUser() {
  const { writeContractAsync, isPending } = useWriteContract();
  const { data: val, refetch } = useReadContract({ address: TRADING_GAME_ADDRESS as `0x${string}`, abi: TRADING_GAME_ABI as any, functionName: "oneTradePerUser" });
  const [err, setErr] = useState<string|null>(null);
  async function toggle() {
    setErr(null);
    try {
      await writeContractAsync({ address: TRADING_GAME_ADDRESS as `0x${string}`, abi: TRADING_GAME_ABI as any, functionName: "adminSetOneTradePerUser", args: [!val] });
      await refetch();
    } catch (e) { setErr((e as Error).message); }
  }
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <div><div className="text-sm font-semibold">One trade per user</div><div className="text-[10px] text-slate-500">Limit to 1 concurrent open trade</div></div>
      <div className="flex items-center gap-2">
        <span className="text-xs font-mono">{val ? "ON" : "OFF"}</span>
        <button onClick={toggle} disabled={isPending} className="h-8 px-3 rounded-lg text-xs font-semibold border border-line-soft hover:bg-bg-700 disabled:opacity-40">{isPending ? "…" : "Toggle"}</button>
      </div>
      {err && <div className="text-[10px] text-down">{err}</div>}
    </div>
  );
}
