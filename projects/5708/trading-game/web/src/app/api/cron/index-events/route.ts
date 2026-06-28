import { NextResponse } from "next/server";
import { ethers } from "ethers";
import { TRADING_GAME_ABI } from "@/lib/contract.generated";
import { supabaseAdmin, isSupabaseConfigured } from "@/lib/supabase";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 60;

// Vercel cron: POST /api/cron/index-events
// Authorization: Bearer <CRON_SECRET>
//
// Scans the contract for TradeOpened / TradeClosed events since the last
// indexed block and reconciles them into Supabase. Catches trades opened
// or closed directly via the contract (not through the API) and any drift
// from failed API mirrors.
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
  if (!rpcUrl || !contractAddress) {
    return NextResponse.json({ error: "rpc/contract not configured" }, { status: 500 });
  }

  const provider = new ethers.JsonRpcProvider(rpcUrl);
  const game = new ethers.Contract(contractAddress, TRADING_GAME_ABI as any, provider);
  const sb = supabaseAdmin();

  let fromBlock = 0;
  const { data: cursor } = await sb.from("index_cursor").select("block").eq("key", "events").maybeSingle();
  if (cursor?.block) fromBlock = cursor.block + 1;

  const latest = await provider.getBlockNumber();
  const toBlock = Math.min(latest, fromBlock + 2000);
  const results = { opened: 0, closed: 0, errors: 0 };

  try {
    const openedEvents = await game.queryFilter(game.filters.TradeOpened(), fromBlock, toBlock);
    for (const e of openedEvents) {
      try {
        const a = e.args as any;
        await sb.from("trades").upsert({
          trade_id: Number(a.tradeId), user_address: a.trader.toLowerCase(),
          pair: "<indexed>", direction: Number(a.direction) === 0 ? "UP" : "DOWN",
          margin: a.margin.toString(), leverage: Number(a.leverage),
          open_price: Number(a.openPrice) / 1e8, tp_pct: Number(a.tpPct), sl_pct: Number(a.slPct),
          status: "open", opened_at: new Date(Number(a.openTimestamp) * 1000).toISOString(),
          tx_open: e.transactionHash,
        }, { onConflict: "trade_id" });
        results.opened++;
      } catch { results.errors++; }
    }

    const closedEvents = await game.queryFilter(game.filters.TradeClosed(), fromBlock, toBlock);
    for (const e of closedEvents) {
      try {
        const a = e.args as any;
        await sb.from("trades").update({
          status: "closed", close_price: Number(a.closePrice) / 1e8,
          pnl: Number(a.pnl) / 1e18, close_reason: "on_chain",
          closed_at: new Date(Number(a.closeTimestamp) * 1000).toISOString(),
          tx_close: e.transactionHash,
        }).eq("trade_id", Number(a.tradeId));
        results.closed++;
      } catch { results.errors++; }
    }

    await sb.from("index_cursor").upsert({ key: "events", block: toBlock, updated_at: new Date().toISOString() }, { onConflict: "key" });
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message, fromBlock, toBlock, results }, { status: 500 });
  }
  return NextResponse.json({ fromBlock, toBlock, results });
}
