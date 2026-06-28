"use client";
import { Header } from "@/components/Header";
import { ActiveTradeCard } from "@/components/ActiveTradeCard";
import { AutoCloseBanner } from "@/components/AutoCloseBanner";
import Link from "next/link";

export default function ActivePage() {
  return (
    <div className="min-h-screen flex flex-col bg-bg-900">
      <Header />
      <main className="flex-1 p-3 sm:p-4 max-w-md mx-auto w-full flex flex-col gap-3">
        <nav className="flex gap-2 text-xs">
          <Link href="/" className="px-3 py-1.5 rounded-lg bg-bg-800 text-slate-400">Trade</Link>
          <Link href="/active" className="px-3 py-1.5 rounded-lg bg-bg-700 text-slate-200">Active</Link>
          <Link href="/history" className="px-3 py-1.5 rounded-lg bg-bg-800 text-slate-400">History</Link>
          <Link href="/admin" className="px-3 py-1.5 rounded-lg bg-bg-800 text-slate-400 ml-auto">Admin</Link>
        </nav>
        <AutoCloseBanner />
        <ActiveTradeCard />
      </main>
    </div>
  );
}
