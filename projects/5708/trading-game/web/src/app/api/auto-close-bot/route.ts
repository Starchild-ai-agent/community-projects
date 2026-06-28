import { ethers } from "ethers";
import { TRADING_GAME_ADDRESS, TRADING_GAME_ABI } from "@/lib/contract.generated";
import { fetchPrice } from "@/lib/price";
import { signClosePrice, newNonce } from "@/lib/oracle";
import { supabaseAdmin, isSupabaseConfigured } from "@/lib/supabase";
import { computePnl, capPnl } from "@/lib/pnl";
import { PAIRS } from "@/lib/types";
import { envChainId, envContractAddress } from "@/lib/config";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 60;

/**
 * POST /api/auto-close-bot
 *
 * Cron-triggered relayer that:
 *   1. Reads all open trades from the Supabase mirror.
 *   2. Fetches a live price for each trade's pair.
 *   3. Computes live PnL; if TP or SL is breached, signs a close payload
 *      with the oracle key and submits `autoCloseTrade()` on-chain via a
 *      funded RELAYER wallet.
 *   4. Mirrors the close back to Supabase.
 *
 * The contract's `autoCloseTrade` is callable by anyone — the oracle
 * signature is what authorizes settlement, not msg.sender. So a single
 * relayer can close trades for all users.
 *
 * Env required:
 *   RELAYER_PRIVATE_KEY   — funded EOA that submits close txs (gas payer)
 *   NEXT_PUBLIC_RPC_URL   — chain RPC
 *   ORACLE_PRIVATE_KEY    — signs close price (same as manual close)
 *   SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY
 *
 * Trigger via Vercel Cron (vercel.json) or external scheduler hitting
 * this endpoint with a secret header.
 */

const BOT_SECRET = process.env.AUTO_CLOSE_BOT_SECRET;

function relayerProvider(): ethers.JsonRpcProvider {
  const rpc = process.env.NEXT_PUBLIC_RPC_URL;
  if (!rpc) throw new Error("NEXT_PUBLIC_RPC_URL missing");
  return new ethers.JsonRpcProvider(rpc);
}

function relayerWallet(): ethers.Wallet {
  const pk = process.env.RELAYER_PRIVATE_KEY;
  if (!pk) throw new Error("RELAYER_PRIVATE_KEY missing");
  return new ethers.Wallet(pk, relayerProvider());
}

export async function POST(req: Request) {
  // Auth: shared secret so randos can't trigger the bot
  if (BOT_SECRET) {
    const provided = req.headers.get("x-bot-secret");
    if (provided !== BOT_SECRET) {
      return Response.json({ error: "unauthorized" }, { status: 401 });
    }
  }

  if (!isSupabaseConfigured()) {
    return Response.json({ error: "supabase not configured" }, { status: 500 });
  }

  const contractAddress = envContractAddress();
  if (!contractAddress || contractAddress === "0x0000000000000000000000000000000000000000") {
    return Response.json({ error: "contract not deployed" }, { status: 500 });
  }

  const chainId = envChainId();
  const sb = supabaseAdmin();
  const { data: openTrades, error } = await sb
    .from("trades")
    .select("*")
    .eq("status", "open")
    .not("trade_id", "is", null);
  if (error) return Response.json({ error: error.message }, { status: 500 });

  const results: Array<{ tradeId: number; action: string; detail?: string }> = [];
  let wallet: ethers.Wallet | null = null;

  for (const row of openTrades || []) {
    const pair = PAIRS.find((p) => p.symbol === row.pair);
    if (!pair) { results.push({ tradeId: row.trade_id, action: "skip", detail: "unknown pair" }); continue; }

    let price: Awaited<ReturnType<typeof fetchPrice>>;
    try { price = await fetchPrice(pair); }
    catch (e) { results.push({ tradeId: row.trade_id, action: "skip", detail: `price fetch failed: ${(e as Error).message}` }); continue; }

    const margin = parseFloat(row.margin);
    const m = computePnl(row.direction, parseFloat(row.open_price), price.price, margin, row.leverage);
    const pnl = capPnl(m.pnl, margin, 40, 40, row.tp_pct, row.sl_pct);
    const roiPct = (pnl / margin) * 100;

    const tpHit = row.tp_pct > 0 && m.pnl >= (margin * row.tp_pct) / 100;
    const slHit = row.sl_pct > 0 && m.pnl <= -(margin * row.sl_pct) / 100;

    if (!tpHit && !slHit) {
      results.push({ tradeId: row.trade_id, action: "monitor", detail: `roi ${roiPct.toFixed(2)}%` });
      continue;
    }

    // TP or SL breached → sign + submit autoCloseTrade
    try {
      if (!wallet) wallet = relayerWallet();
      const nonce = newNonce();
      const signature = signClosePrice({
        tradeId: row.trade_id,
        priceScaled: price.priceScaled,
        timestamp: price.timestamp,
        nonce,
        chainId,
        contractAddress,
      });

      const contract = new ethers.Contract(contractAddress, TRADING_GAME_ABI as any, wallet);
      const tx = await contract.autoCloseTrade(
        row.trade_id,
        price.priceScaled,
        price.timestamp,
        nonce,
        signature,
        { gasLimit: 300_000 },
      );
      await tx.wait();

      // Mirror close to Supabase
      await sb.from("trades").update({
        status: "closed",
        close_price: price.price,
        pnl,
        roi_pct: roiPct,
        closed_at: new Date().toISOString(),
        close_reason: tpHit ? "TP" : "SL",
        tx_close: tx.hash,
      }).eq("trade_id", row.trade_id);

      results.push({ tradeId: row.trade_id, action: tpHit ? "tp-closed" : "sl-closed", detail: `tx ${tx.hash.slice(0,10)}… pnl ${pnl.toFixed(4)}` });
    } catch (e) {
      results.push({ tradeId: row.trade_id, action: "error", detail: (e as Error).message });
    }
  }

  return Response.json({ processed: results.length, results });
}
