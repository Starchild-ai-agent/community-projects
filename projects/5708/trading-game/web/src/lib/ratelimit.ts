// Simple in-memory rate limiter (per IP).
// For production multi-instance deploys, swap for Upstash Redis or Vercel KV.

const buckets = new Map<string, { count: number; resetAt: number }>();

export function rateLimit(key: string, maxPerMinute: number): boolean {
  const now = Date.now();
  const b = buckets.get(key);
  if (!b || b.resetAt < now) {
    buckets.set(key, { count: 1, resetAt: now + 60_000 });
    return true;
  }
  if (b.count >= maxPerMinute) return false;
  b.count += 1;
  return true;
}
