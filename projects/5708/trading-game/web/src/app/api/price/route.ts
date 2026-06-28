import { NextResponse } from "next/server";
import { PAIRS } from "@/lib/types";
import { fetchPrice } from "@/lib/price";
import { rateLimit } from "@/lib/ratelimit";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// GET /api/price?pair=SOL-PERP
export async function GET(req: Request) {
  const ip = req.headers.get("x-forwarded-for")?.split(",")[0] || "anon";
  if (!rateLimit(`price:${ip}`, 60)) {
    return NextResponse.json({ error: "rate limited" }, { status: 429 });
  }
  const { searchParams } = new URL(req.url);
  const symbol = searchParams.get("pair") || "SOL-PERP";
  const pair = PAIRS.find((p) => p.symbol === symbol);
  if (!pair) return NextResponse.json({ error: "unknown pair" }, { status: 400 });
  try {
    const payload = await fetchPrice(pair);
    return NextResponse.json(payload);
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 502 });
  }
}
