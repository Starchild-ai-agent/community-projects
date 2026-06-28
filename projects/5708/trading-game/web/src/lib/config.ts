import { PAIRS } from "./types";

export function getPair(symbol: string) {
  return PAIRS.find((p) => p.symbol === symbol);
}

export function isAdmin(address?: string | null): boolean {
  if (!address) return false;
  const list = (process.env.ADMIN_WALLETS || "").split(",").map((s) => s.trim().toLowerCase());
  return list.includes(address.toLowerCase());
}

export function envChainId(): number {
  return parseInt(process.env.NEXT_PUBLIC_CHAIN_ID || "11155111", 10);
}

export function envContractAddress(): string {
  return (
    process.env.NEXT_PUBLIC_TRADING_GAME_ADDRESS ||
    (typeof window !== "undefined" && (window as any).__TRADING_GAME_ADDRESS) ||
    ""
  );
}
