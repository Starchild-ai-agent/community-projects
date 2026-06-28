import { createClient } from "@supabase/supabase-js";

/**
 * Supabase service client (server-only).
 * Uses the service-role key — NEVER expose this to the browser.
 * The backend mirrors on-chain TradeOpened/TradeClosed events here for fast
 * UI queries; the on-chain contract remains the source of truth for settlement.
 */

let _client: ReturnType<typeof createClient> | null = null;

export function supabaseAdmin() {
  if (_client) return _client;
  const url = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error("Supabase env missing (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY)");
  _client = createClient(url, key, { auth: { persistSession: false } });
  return _client;
}

export function isSupabaseConfigured(): boolean {
  return !!(process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL) && !!process.env.SUPABASE_SERVICE_ROLE_KEY;
}
