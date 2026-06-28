import type { PairConfig, PricePayload } from "./types";

/**
 * Live price fetcher.
 *
 * Providers:
 *   - "binance:SYMBOL"   → Binance public ticker (no key needed)
 *   - "coingecko:COINID" → CoinGecko simple price (optional key)
 *   - "mock:BASEPRICE"   → deterministic-ish simulation for local dev
 *
 * All prices are returned as { price, priceScaled: price*1e8, timestamp }.
 * The backend signs priceScaled + timestamp; the contract verifies the sig
 * and never trusts a frontend-submitted number.
 */

async function fetchBinance(symbol: string): Promise<number> {
  const url = `https://api.binance.com/api/v3/ticker/price?symbol=${symbol}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`binance ${symbol} ${res.status}`);
  const j = (await res.json()) as { price: string };
  return parseFloat(j.price);
}

async function fetchCoingecko(coinId: string): Promise<number> {
  const key = process.env.COINGECKO_API_KEY;
  const base = key
    ? "https://pro-api.coingecko.com/api/v3"
    : "https://api.coingecko.com/api/v3";
  const headers: Record<string, string> = key ? { "x-cg-pro-api-key": key } : {};
  const url = `${base}/simple/price?ids=${coinId}&vs_currencies=usd`;
  const res = await fetch(url, { headers, cache: "no-store" });
  if (!res.ok) throw new Error(`coingecko ${coinId} ${res.status}`);
  const j = (await res.json()) as Record<string, { usd: number }>;
  return j[coinId].usd;
}

function mockPrice(base: number): number {
  const shock = (Math.random() - 0.5) * 0.002; // ±0.1%
  return base * (1 + shock);
}

export async function fetchPrice(pair: PairConfig): Promise<PricePayload> {
  const [provider, arg] = pair.priceProvider.split(":");
  let price: number;
  if (provider === "binance") price = await fetchBinance(arg);
  else if (provider === "coingecko") price = await fetchCoingecko(arg);
  else if (provider === "mock") price = mockPrice(parseFloat(arg));
  else throw new Error(`unknown provider: ${pair.priceProvider}`);

  if (!isFinite(price) || price <= 0) throw new Error("bad price");

  return {
    symbol: pair.symbol,
    price,
    priceScaled: BigInt(Math.round(price * 1e8)),
    timestamp: Math.floor(Date.now() / 1000),
  };
}
