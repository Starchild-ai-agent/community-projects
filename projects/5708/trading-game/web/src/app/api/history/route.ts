import { NextResponse } from "next/server";
import { supabaseAdmin, isSupabaseConfigured } from "@/lib/supabase";
import { rateLimit } from "@/lib/ratelimit";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(req: Request) {
  const ip = req.headers.get("x-forwarded-for")?.split(",")[0] || "anon";
  if (!rateLimit(`history:${ip}`, 30)) return NextResponse.json({ error: "rate limited" }, { status: 429 });
  if (!isSupabaseConfigured()) return NextResponse.json({ trades: [] });
  const { searchParams } = new URL(req.url);
  const user = searchParams.get("user")?.toLowerCase();
  try {
    let q = supabaseAdmin().from("trades").select("*").order("opened_at", { ascending: false }).limit(100);
    if (user) q = q.eq("user_address", user);
    const { data, error } = await q;
    if (error) throw error;
    return NextResponse.json({ trades: data });
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }
}
