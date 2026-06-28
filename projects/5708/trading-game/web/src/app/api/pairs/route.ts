import { NextResponse } from "next/server";
import { PAIRS } from "@/lib/types";
import { fetchPrice } from "@/lib/price";
import { rateLimit } from "@/lib/ratelimit";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// GET /api/pairs → supported pairs + live prices
export async function GET(req: Request) {
  const ip = req.headers.get("x-forwarded-for")?.split(",")[0] || "anon";
  if (!rateLimit(`pairs:${ip}`, 30)) {
    return NextResponse.json({ error: "rate limited" }, { status: 429 });
  }
  try {
    const out = await Promise.all(
      PAIRS.map(async (p) => {
        try {
          const px = await fetchPrice(p);
          return { ...p, price: px.price, timestamp: px.timestamp };
        } catch {
          return { ...p, price: null, timestamp: null };
        }
      })
    );
    return NextResponse.json({ pairs: out });
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }
}
