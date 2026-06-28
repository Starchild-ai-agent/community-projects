import { NextResponse } from "next/server";
import { ethers } from "ethers";
import { TRADING_GAME_ABI } from "@/lib/contract.generated";
import { fetchPrice } from "@/lib/price";
import { signClosePrice, newNonce } from "@/lib/oracle";
import { supabaseAdmin, isSupabaseConfigured } from "@/lib/supabase";
import { computePnl, capPnl } from "@/lib/pnl";
import { PAIRS } from "@/lib/types";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 60;

// Vercel cron: POST /api/cron/auto-close
// Authorization: Bearer <CRON_SECRET>
//
// Scans all OPEN trades in Supabase, fetches the current mark price,
// and auto-closes any whose TP or SL threshold has been breached.
// Signs the close payload and stores it in `pending_closes` for the
// user to submit from the frontend (contract requires msg.sender == trader).
export async function POST(req: Request) {
  const auth = req.headers.get("authorization");
  const secret = process.env.CRON_SECRET;
  if (!secret || auth !== `Bearer ${secret}`) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  if (!isSupabaseConfigured()) {
    return NextResponse.json({ error: "supabase not configured" }, { status: 500 });
  }
  const rpcUrl = process.env.NEXT_PUBLIC_RPC_URL;
  const contractAddress = process.env.NEXT_PUBLIC_TRADING_GAME_ADDRESS;
  const chainId = parseInt(process.env.NEXT_PUBLIC_CHAIN_ID || "11155111", 10);
  if (!rpcUrl || !contractAddress) {
    return NextResponse.json({ error: "rpc/contract not configured" }, { status: 500 });
  }

  const provider = new ethers.JsonRpcProvider(rpcUrl);
  const game = new ethers.Contract(contractAddress, TRADING_GAME_ABI as any, provider);
  const sb = supabaseAdmin();

  const { data: openTrades, error } = await sb
    .from("trades").select("*").eq("status", "open")
    .order("opened_at", { ascending: true }).limit(200);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const results: Array<{ tradeId: number; action: string; reason: string }> = [];

  for (const row of openTrades || []) {
    try {
      const onChain = await game.getTrade(row.trade_id).catch(() => null);
      if (!onChain || onChain.closed) {
        await sb.from("trades").update({ status: "closed", close_reason: "manual_or_external" }).eq("id", row.id);
        results.push({ tradeId: row.trade_id, action: "skip", reason: "closed off-platform" });
        continue;
      }
      if (onChain.trader.toLowerCase() !== row.user_address.toLowerCase()) {
        results.push({ tradeId: row.trade_id, action: "skip", reason: "owner mismatch" });
        continue;
      }
      const pair = PAIRS.find((p) => p.symbol === row.pair);
      if (!pair) { results.push({ tradeId: row.trade_id, action: "skip", reason: "unknown pair" }); continue; }

      const price = await fetchPrice(pair);
      const margin = parseFloat(row.margin);
      const m = computePnl(row.direction, parseFloat(row.open_price), price.price, margin, row.leverage);

      const hitTP = row.tp_pct > 0 && m.pnl >= (margin * row.tp_pct) / 100;
      const hitSL = row.sl_pct > 0 && m.pnl <= -(margin * row.sl_pct) / 100;

      if (!hitTP && !hitSL) {
        results.push({ tradeId: row.trade_id, action: "skip", reason: "not at tp/sl" });
        continue;
      }

      const nonce = newNonce();
      const signature = signClosePrice({
        tradeId: row.trade_id, priceScaled: price.priceScaled,
        timestamp: price.timestamp, nonce, chainId, contractAddress,
      });

      await sb.from("pending_closes").upsert({
        trade_id: row.trade_id, user_address: row.user_address,
        close_price: price.price, price_scaled: price.priceScaled.toString(),
        timestamp: price.timestamp, nonce, signature,
        reason: hitTP ? "TP" : "SL",
        created_at: new Date().toISOString(), submitted: false,
      }, { onConflict: "trade_id" });

      await sb.from("trades").update({ status: "pending_close" }).eq("id", row.id);
      results.push({ tradeId: row.trade_id, action: hitTP ? "tp" : "sl", reason: `signed @ ${price.price}` });
    } catch (e) {
      results.push({ tradeId: row.trade_id, action: "skip", reason: (e as Error).message });
    }
  }
  return NextResponse.json({ scanned: openTrades?.length || 0, results });
}
