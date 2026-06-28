import { NextResponse } from "next/server";
import { ethers } from "ethers";
import type { OpenTradeRequest, OpenTradeResponse } from "@/lib/types";
import { PAIRS } from "@/lib/types";
import { fetchPrice } from "@/lib/price";
import { signOpenPrice, oracleSignerAddress } from "@/lib/oracle";
import { envChainId, envContractAddress } from "@/lib/config";
import { rateLimit } from "@/lib/ratelimit";
import { supabaseAdmin, isSupabaseConfigured } from "@/lib/supabase";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// POST /api/open-sign
// Body: OpenTradeRequest
// Returns a signed open-price payload the user submits to the contract.
export async function POST(req: Request) {
  const ip = req.headers.get("x-forwarded-for")?.split(",")[0] || "anon";
  const limit = parseInt(process.env.RATE_LIMIT_OPEN || "10", 10);
  if (!rateLimit(`open:${ip}`, limit)) {
    return NextResponse.json({ error: "rate limited" }, { status: 429 });
  }

  let body: OpenTradeRequest;
  try {
    body = (await req.json()) as OpenTradeRequest;
  } catch {
    return NextResponse.json({ error: "bad json" }, { status: 400 });
  }

  const pair = PAIRS.find((p) => p.symbol === body.pair);
  if (!pair) return NextResponse.json({ error: "unknown pair" }, { status: 400 });
  if (body.direction !== "UP" && body.direction !== "DOWN")
    return NextResponse.json({ error: "bad direction" }, { status: 400 });
  if (!ethers.isAddress(body.userAddress))
    return NextResponse.json({ error: "bad address" }, { status: 400 });

  const margin = BigInt(body.margin || "0");
  if (margin <= 0n) return NextResponse.json({ error: "bad margin" }, { status: 400 });

  if (body.leverage <= 0 || body.leverage > pair.maxLeverage)
    return NextResponse.json({ error: "bad leverage" }, { status: 400 });
  if (body.tpPct < 0 || body.tpPct > 40)
    return NextResponse.json({ error: "tp out of range (max 40)" }, { status: 400 });
  if (body.slPct < 0 || body.slPct > 40)
    return NextResponse.json({ error: "sl out of range (max 40)" }, { status: 400 });

  const contractAddress = envContractAddress();
  if (!contractAddress || contractAddress === "0x0000000000000000000000000000000000000000")
    return NextResponse.json({ error: "contract not deployed" }, { status: 500 });

  try {
    const price = await fetchPrice(pair);
    const pairId = ethers.keccak256(ethers.toUtf8Bytes(pair.symbol));
    const chainId = envChainId();

    const signature = signOpenPrice({
      pairId,
      priceScaled: price.priceScaled,
      timestamp: price.timestamp,
      trader: body.userAddress,
      chainId,
      contractAddress,
    });

    // Sanity: derived oracle address must match env ORACLE_SIGNER_ADDRESS
    const expected = process.env.ORACLE_SIGNER_ADDRESS?.toLowerCase();
    if (expected && oracleSignerAddress().toLowerCase() !== expected) {
      return NextResponse.json({ error: "oracle signer mismatch" }, { status: 500 });
    }

    // Mirror to Supabase (best-effort — contract is source of truth)
    if (isSupabaseConfigured()) {
      try {
        await supabaseAdmin().from("trades").insert({
          user_address: body.userAddress.toLowerCase(),
          pair: pair.symbol,
          direction: body.direction,
          margin: body.margin,
          leverage: body.leverage,
          open_price: price.price,
          tp_pct: body.tpPct,
          sl_pct: body.slPct,
          status: "pending",
          opened_at: new Date().toISOString(),
        });
      } catch (e) {
        console.warn("supabase insert failed:", (e as Error).message);
      }
    }

    const res: OpenTradeResponse = {
      openPrice: price.price,
      priceScaled: price.priceScaled,
      timestamp: price.timestamp,
      pairId,
      signature,
      chainId,
      contractAddress,
    };
    return NextResponse.json(res);
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }
}
