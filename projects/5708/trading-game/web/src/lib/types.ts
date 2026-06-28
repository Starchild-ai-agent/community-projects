// Shared types used by frontend + backend.

export type Direction = "UP" | "DOWN";

export interface PairConfig {
  symbol: string;        // "SOL-PERP"
  label: string;         // "SOL/USDT"
  priceProvider: string; // "binance:SOLUSDT" | "coingecko:solana"
  defaultLeverage: number;
  maxLeverage: number;
  decimals: number;      // display decimals
}

export const PAIRS: PairConfig[] = [
  { symbol: "SOL-PERP", label: "SOL/USDT", priceProvider: "binance:SOLUSDT", defaultLeverage: 1000, maxLeverage: 1000, decimals: 4 },
  { symbol: "BTC-PERP", label: "BTC/USDT", priceProvider: "binance:BTCUSDT", defaultLeverage: 1000, maxLeverage: 1000, decimals: 2 },
  { symbol: "ETH-PERP", label: "ETH/USDT", priceProvider: "binance:ETHUSDT", defaultLeverage: 1000, maxLeverage: 1000, decimals: 2 },
];

export interface PricePayload {
  symbol: string;
  price: number;          // human-readable
  priceScaled: bigint;    // price * 1e8 (for on-chain)
  timestamp: number;      // unix seconds
}

export interface OpenTradeRequest {
  pair: string;
  direction: Direction;
  margin: string;         // base units string
  leverage: number;
  tpPct: number;
  slPct: number;
  userAddress: string;
}

export interface OpenTradeResponse {
  openPrice: number;
  priceScaled: bigint;
  timestamp: number;
  pairId: string;         // bytes32 hex
  signature: string;      // 65-byte hex sig from oracle
  chainId: number;
  contractAddress: string;
}

export interface CloseTradeRequest {
  tradeId: number;
  userAddress: string;
}

export interface CloseTradeResponse {
  tradeId: number;
  closePrice: number;
  priceScaled: bigint;
  timestamp: number;
  nonce: string;          // bytes32 hex
  signature: string;
  chainId: number;
  contractAddress: string;
  pnl: number;            // human-readable estimate
  roiPct: number;
}

export interface TradeRow {
  id: string;             // supabase uuid
  trade_id: number;       // on-chain id
  user_address: string;
  pair: string;
  direction: Direction;
  margin: string;
  leverage: number;
  open_price: number;
  close_price: number | null;
  tp_pct: number;
  sl_pct: number;
  status: "open" | "closed";
  pnl: number | null;
  roi_pct: number | null;
  opened_at: string;
  closed_at: string | null;
  close_reason: string | null;
}
