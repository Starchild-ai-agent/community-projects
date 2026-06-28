import { NextResponse } from "next/server";
import { ethers } from "ethers";
import type { CloseTradeRequest, CloseTradeResponse } from "@/lib/types";
import { PAIRS } from "@/lib/types";
import { fetchPrice } from "@/lib/price";
import { signClosePrice, newNonce, oracleSignerAddress } from "@/lib/oracle";
import { envChainId, envContractAddress } from "@/lib/config";
import { rateLimit } from "@/lib/ratelimit";
import { supabaseAdmin, isSupabaseConfigured } from "@/lib/supabase";
import { computePnl, capPnl } from "@/lib/pnl";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// POST /api/close-trade
// Body: CloseTradeRequest { tradeId, userAddress }
// Backend validates ownership + freshness, fetches a live close price,
// signs it, and returns the payload the user submits to closeTrade().
export async function POST(req: Request) {
  const ip = req.headers.get("x-forwarded-for")?.split(",")[0] || "anon";
  const limit = parseInt(process.env.RATE_LIMIT_CLOSE || "20", 10);
  if (!rateLimit(`close:${ip}`, limit)) {
    return NextResponse.json({ error: "rate limited" }, { status: 429 });
  }

  let body: CloseTradeRequest;
  try {
    body = (await req.json()) as CloseTradeRequest;
  } catch {
    return NextResponse.json({ error: "bad json" }, { status: 400 });
  }
  if (!Number.isInteger(body.tradeId) || body.tradeId <= 0)
    return NextResponse.json({ error: "bad tradeId" }, { status: 400 });
  if (!ethers.isAddress(body.userAddress))
    return NextResponse.json({ error: "bad address" }, { status: 400 });

  const contractAddress = envContractAddress();
  if (!contractAddress || contractAddress === "0x0000000000000000000000000000000000000000")
    return NextResponse.json({ error: "contract not deployed" }, { status: 500 });

  // --- Validate against Supabase mirror ---
  // The contract is the ultimate source of truth, but we check the DB mirror
  // here to (a) prevent duplicate close requests and (b) verify ownership
  // before signing.
  let tradeRow: any = null;
  if (isSupabaseConfigured()) {
    try {
      const sb = supabaseAdmin();
      const { data, error } = await sb
        .from("trades")
        .select("*")
        .eq("trade_id", body.tradeId)
        .eq("user_address", body.userAddress.toLowerCase())
        .maybeSingle();
      if (error) throw error;
      tradeRow = data;
      if (!tradeRow) return NextResponse.json({ error: "trade not found" }, { status: 404 });
      if (tradeRow.status === "closed")
        return NextResponse.json({ error: "trade already closed" }, { status: 409 });
      if (tradeRow.user_address.toLowerCase() !== body.userAddress.toLowerCase())
        return NextResponse.json({ error: "not owner" }, { status: 403 });
    } catch (e) {
      console.warn("supabase lookup failed:", (e as Error).message);
      // Continue — contract is source of truth; we'll sign and let contract reject.
    }
  }

  const pair = PAIRS.find((p) => p.symbol === tradeRow?.pair) || PAIRS[0];
  try {
    const price = await fetchPrice(pair);
    const chainId = envChainId();
    const nonce = newNonce();

    const signature = signClosePrice({
      tradeId: body.tradeId,
      priceScaled: price.priceScaled,
      timestamp: price.timestamp,
      nonce,
      chainId,
      contractAddress,
    });

    // PnL estimate (capped) for UI feedback
    let pnl = 0;
    let roiPct = 0;
    if (tradeRow) {
      const m = computePnl(
        tradeRow.direction,
        parseFloat(tradeRow.open_price),
        price.price,
        parseFloat(tradeRow.margin),
        tradeRow.leverage
      );
      pnl = capPnl(m.pnl, parseFloat(tradeRow.margin), 100, 50, tradeRow.tp_pct, tradeRow.sl_pct);
      roiPct = (pnl / parseFloat(tradeRow.margin)) * 100;
    }

    const expected = process.env.ORACLE_SIGNER_ADDRESS?.toLowerCase();
    if (expected && oracleSignerAddress().toLowerCase() !== expected) {
      return NextResponse.json({ error: "oracle signer mismatch" }, { status: 500 });
    }

    const res: CloseTradeResponse = {
      tradeId: body.tradeId,
      closePrice: price.price,
      priceScaled: price.priceScaled,
      timestamp: price.timestamp,
      nonce,
      signature,
      chainId,
      contractAddress,
      pnl,
      roiPct,
    };
    return NextResponse.json(res);
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }
}
