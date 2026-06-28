import { NextResponse } from "next/server";
import { supabaseAdmin, isSupabaseConfigured } from "@/lib/supabase";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// GET /api/cron/keeper-submit
// Returns signed close payloads waiting for the user to submit.
// The contract requires msg.sender == trade.trader, so a keeper cannot
// submit on behalf of users. The frontend polls this and prompts the user.
export async function GET(req: Request) {
  const auth = req.headers.get("authorization");
  const secret = process.env.CRON_SECRET;
  if (!secret || auth !== `Bearer ${secret}`) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  if (!isSupabaseConfigured()) {
    return NextResponse.json({ pending: [] });
  }
  const user = new URL(req.url).searchParams.get("user")?.toLowerCase();
  const sb = supabaseAdmin();
  let q = sb.from("pending_closes").select("*").eq("submitted", false).order("created_at", { ascending: true }).limit(50);
  if (user) q = q.eq("user_address", user);
  const { data: pending, error } = await q;
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  return NextResponse.json({
    pending: (pending || []).map((p) => ({
      tradeId: p.trade_id, userAddress: p.user_address, closePrice: p.close_price,
      priceScaled: p.price_scaled, timestamp: p.timestamp, nonce: p.nonce,
      signature: p.signature, reason: p.reason,
    })),
  });
}
