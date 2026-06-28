"use client";
import { usePendingAutoClose } from "@/hooks/usePendingAutoClose";

export function AutoCloseBanner() {
  const { pending, submitClose, submitting } = usePendingAutoClose();
  if (!pending) return null;
  return (
    <div className="rounded-xl border border-warn/50 bg-warn/10 p-3 mb-3 animate-pulseRed">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-bold text-warn">
            {pending.reason === "TP" ? "Take Profit hit!" : "Stop Loss hit!"}
          </div>
          <div className="text-[10px] text-slate-400">
            Trade #{pending.tradeId} · close @ {pending.closePrice.toFixed(4)}
          </div>
        </div>
        <button
          onClick={submitClose}
          disabled={submitting}
          className="h-9 px-4 rounded-lg text-xs font-bold bg-warn text-bg-900 hover:brightness-110 disabled:opacity-40"
        >
          {submitting ? "…" : "Close Now"}
        </button>
      </div>
    </div>
  );
}