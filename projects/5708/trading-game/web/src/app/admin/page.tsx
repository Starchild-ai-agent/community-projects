"use client";
import { Header } from "@/components/Header";
import { useAccount, useReadContract } from "wagmi";
import { TRADING_GAME_ADDRESS, TRADING_GAME_ABI } from "@/lib/contract.generated";
import Link from "next/link";
import {
  PauseToggle, SetRiskParams, SetOracleSigner,
  SetPairForm, SetFeeRecipient, SetOneTradePerUser,
} from "@/components/AdminActions";

export default function AdminPage() {
  const { address } = useAccount();
  const isAdmin = (() => {
    const list = (process.env.NEXT_PUBLIC_ADMIN_WALLETS || process.env.ADMIN_WALLETS || "")
      .split(",").map((s) => s.trim().toLowerCase());
    return !!address && list.includes(address.toLowerCase());
  })();
  const { data: oracle } = useReadContract({ address: TRADING_GAME_ADDRESS as `0x${string}`, abi: TRADING_GAME_ABI as any, functionName: "oracleSigner" });
  const { data: token } = useReadContract({ address: TRADING_GAME_ADDRESS as `0x${string}`, abi: TRADING_GAME_ABI as any, functionName: "marginToken" });

  return (
    <div className="min-h-screen flex flex-col bg-bg-900">
      <Header />
      <main className="flex-1 p-3 sm:p-4 max-w-md mx-auto w-full">
        <nav className="flex gap-2 text-xs mb-3">
          <Link href="/" className="px-3 py-1.5 rounded-lg bg-bg-800 text-slate-400">Trade</Link>
          <Link href="/active" className="px-3 py-1.5 rounded-lg bg-bg-800 text-slate-400">Active</Link>
          <Link href="/history" className="px-3 py-1.5 rounded-lg bg-bg-800 text-slate-400">History</Link>
          <Link href="/admin" className="px-3 py-1.5 rounded-lg bg-bg-700 text-slate-200 ml-auto">Admin</Link>
        </nav>
        {!address && <div className="text-xs text-slate-500">Connect wallet.</div>}
        {address && !isAdmin && (
          <div className="rounded-xl border border-down/40 bg-down/10 p-3 text-xs text-down">
            Your wallet ({address.slice(0,6)}…{address.slice(-4)}) is not in ADMIN_WALLETS.
          </div>
        )}
        {address && isAdmin && (
          <div className="space-y-3">
            <div className="rounded-xl border border-line/60 bg-bg-800/60 p-4 text-xs space-y-1">
              <h2 className="text-sm font-semibold mb-2">Contract state</h2>
              <div className="flex justify-between"><span className="text-slate-500">Address</span><span className="font-mono text-slate-300 text-[10px]">{TRADING_GAME_ADDRESS}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">Oracle</span><span className="font-mono text-slate-300 text-[10px]">{(oracle as string|undefined)?.slice(0,10)}…</span></div>
              <div className="flex justify-between"><span className="text-slate-500">Margin token</span><span className="font-mono text-slate-300 text-[10px]">{(token as string|undefined)?.slice(0,10)}…</span></div>
            </div>
            <div className="rounded-xl border border-line/60 bg-bg-800/60 p-4 space-y-3 divide-y divide-line/40">
              <PauseToggle />
              <SetRiskParams />
              <SetOracleSigner />
              <SetPairForm />
              <SetFeeRecipient />
              <SetOneTradePerUser />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
