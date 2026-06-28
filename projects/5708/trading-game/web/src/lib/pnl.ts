// PnL math — MUST match the contract's _settle exactly.
// See contracts/contracts/TradingGame.sol

import type { Direction } from "./types";

export const PRICE_SCALE = 1e8;

/**
 * Compute PnL given human-readable prices + margin + leverage.
 * Returns { pnl, roiPct, priceMovePct }.
 *
 *   priceMovePct = ((close - open) / open) * 100   [UP]
 *   priceMovePct = ((open - close) / open) * 100   [DOWN]
 *   leveragedROI = priceMovePct * leverage
 *   pnl = margin * leveragedROI / 100
 */
export function computePnl(
  direction: Direction,
  openPrice: number,
  closePrice: number,
  margin: number,
  leverage: number
): { pnl: number; roiPct: number; priceMovePct: number } {
  const dir = direction === "UP" ? 1 : -1;
  const priceMovePct = ((closePrice - openPrice) / openPrice) * 100 * dir;
  const roiPct = priceMovePct * leverage;
  const pnl = (margin * roiPct) / 100;
  return { pnl, roiPct, priceMovePct };
}

export const MAX_TP_PCT = 40;
export const MAX_SL_PCT = 40;

export function capPnl(
  pnl: number,
  margin: number,
  maxProfitPct: number,
  maxLossPct: number,
  tpPct: number,
  slPct: number
): number {
  const maxProfit = (margin * Math.min(maxProfitPct, MAX_TP_PCT)) / 100;
  const maxLoss = -(margin * Math.min(maxLossPct, MAX_SL_PCT)) / 100;
  let p = pnl;
  if (p > maxProfit) p = maxProfit;
  if (p < maxLoss) p = maxLoss;
  if (tpPct > 0 && p >= (margin * tpPct) / 100) p = (margin * tpPct) / 100;
  if (slPct > 0 && p <= -(margin * slPct) / 100) p = -(margin * slPct) / 100;
  return p;
}
