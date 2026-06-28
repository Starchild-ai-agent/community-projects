"use client";
import { useEffect, useState } from "react";
import { useAccount, useWriteContract } from "wagmi";
import { TRADING_GAME_ADDRESS, TRADING_GAME_ABI } from "@/lib/contract.generated";

interface PendingClose {
  tradeId: number;
  userAddress: string;
  closePrice: number;
  priceScaled: string;
  timestamp: number;
  nonce: string;
  signature: string;
  reason: string;
}

// Polls /api/cron/keeper-submit for signed close payloads.
export function usePendingAutoClose() {
  const { address } = useAccount();
  const { writeContractAsync } = useWriteContract();
  const [pending, setPending] = useState<PendingClose | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!address) return;
    const poll = () => {
      fetch(`/api/cron/keeper-submit?user=${address}`, {
        headers: { authorization: `Bearer ${process.env.NEXT_PUBLIC_CRON_SECRET || ""}` },
      })
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => {
          const mine = d?.pending?.find(
            (p: PendingClose) => p.userAddress.toLowerCase() === address.toLowerCase()
          );
          setPending(mine || null);
        })
        .catch(() => {});
    };
    poll();
    const id = setInterval(poll, 15000);
    return () => clearInterval(id);
  }, [address]);

  async function submitClose() {
    if (!pending) return;
    setSubmitting(true);
    try {
      await writeContractAsync({
        address: TRADING_GAME_ADDRESS as `0x${string}`,
        abi: TRADING_GAME_ABI as any,
        functionName: "closeTrade",
        args: [
          BigInt(pending.tradeId),
          BigInt(pending.priceScaled),
          BigInt(pending.timestamp),
          pending.nonce as `0x${string}`,
          pending.signature as `0x${string}`,
        ],
      });
      setPending(null);
    } finally {
      setSubmitting(false);
    }
  }

  return { pending, submitClose, submitting };
}
