"use client";
import { useAccount, useBalance, useReadContract } from "wagmi";
import { ConnectButton } from "@rainbow-me/rainbowkit";
import { TRADING_GAME_ADDRESS, TRADING_GAME_ABI } from "@/lib/contract.generated";
import { formatUnits } from "viem";

const ERC20_ABI = [
  { inputs: [{ name: "a", type: "address" }], name: "balanceOf", outputs: [{ name: "", type: "uint256" }], stateMutability: "view", type: "function" },
] as const;

export function Header() {
  const { address } = useAccount();
  const token = process.env.NEXT_PUBLIC_MARGIN_TOKEN_ADDRESS as `0x${string}` | undefined;
  const { data: tokenBal } = useBalance({
    address,
    token: token,
    query: { enabled: !!address && !!token },
  });
  const { data: deposited } = useReadContract({
    address: TRADING_GAME_ADDRESS as `0x${string}`,
    abi: TRADING_GAME_ABI as any,
    functionName: "deposited",
    args: [address || "0x0"],
    query: { enabled: !!address },
  });

  return (
    <header className="h-14 shrink-0 border-b border-line/60 bg-bg-800/80 backdrop-blur flex items-center justify-between px-3 sm:px-4">
      <div className="flex items-center gap-2">
        <div className="h-7 w-7 rounded-md bg-gradient-to-br from-up to-emerald-700 grid place-items-center text-bg-900 font-black">T</div>
        <div className="leading-none">
          <div className="text-sm font-bold">Trading<span className="text-up">Game</span></div>
          <div className="text-[10px] text-slate-500 hidden sm:block">1000x Perp</div>
        </div>
      </div>
      <div className="flex items-center gap-3">
        {address && (
          <div className="hidden sm:flex flex-col items-end leading-none">
            <span className="text-[10px] text-slate-500">
              {process.env.NEXT_PUBLIC_MARGIN_TOKEN_SYMBOL || "USDT"} balance
            </span>
            <span className="font-mono text-sm">
              {tokenBal ? parseFloat(tokenBal.formatted).toFixed(2) : "—"}
            </span>
            {deposited !== undefined && (
              <span className="text-[10px] text-slate-500">
                deposited: {formatUnits(deposited as bigint, 18)}
              </span>
            )}
          </div>
        )}
        <ConnectButton />
      </div>
    </header>
  );
}
