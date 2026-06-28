-- TradingGame Supabase schema
-- The on-chain contract is the source of truth for settlement.
-- This mirror is for fast UI queries + duplicate-close prevention + auto-close bot.

create extension if not exists "pgcrypto";

create table if not exists public.trades (
  id uuid primary key default gen_random_uuid(),
  trade_id bigint unique,
  user_address text not null,
  pair text not null,
  direction text not null check (direction in ('UP','DOWN')),
  margin text not null,
  leverage int not null,
  open_price numeric not null,
  close_price numeric,
  tp_pct numeric not null default 0,
  sl_pct numeric not null default 0,
  status text not null default 'pending' check (status in ('pending','open','pending_close','closed')),
  pnl numeric,
  roi_pct numeric,
  close_reason text,
  opened_at timestamptz not null default now(),
  closed_at timestamptz,
  tx_open text,
  tx_close text
);
create index if not exists trades_user_idx on public.trades(user_address);
create index if not exists trades_status_idx on public.trades(status);
create index if not exists trades_trade_id_idx on public.trades(trade_id);

alter table public.trades enable row level security;
create policy "own trades read" on public.trades for select using (auth.jwt() ->> 'sub' = user_address);
create policy "service all" on public.trades for all using (true) with check (true);

-- ---- Pending auto-close payloads (signed by oracle, waiting for user to submit) ----
create table if not exists public.pending_closes (
  trade_id bigint primary key,
  user_address text not null,
  close_price numeric not null,
  price_scaled text not null,
  timestamp bigint not null,
  nonce text not null,
  signature text not null,
  reason text not null,
  created_at timestamptz not null default now(),
  submitted boolean not null default false
);
create index if not exists pending_user_idx on public.pending_closes(user_address);
create index if not exists pending_submitted_idx on public.pending_closes(submitted);

alter table public.pending_closes enable row level security;
create policy "own pending read" on public.pending_closes for select using (auth.jwt() ->> 'sub' = user_address);
create policy "service all pending" on public.pending_closes for all using (true) with check (true);

-- ---- Event indexer cursor ----
create table if not exists public.index_cursor (
  key text primary key,
  block bigint not null default 0,
  updated_at timestamptz not null default now()
);
insert into public.index_cursor (key, block) values ('events', 0) on conflict (key) do nothing;

-- ---- Pair settings ----
create table if not exists public.pairs (
  symbol text primary key,
  label text not null,
  supported boolean not null default true,
  max_leverage int not null default 1000,
  default_leverage int not null default 1000,
  updated_at timestamptz not null default now()
);
insert into public.pairs (symbol, label) values
  ('SOL-PERP','SOL/USDT'),
  ('BTC-PERP','BTC/USDT'),
  ('ETH-PERP','ETH/USDT')
on conflict (symbol) do nothing;

-- ---- Risk params ----
create table if not exists public.risk_params (
  id int primary key default 1,
  max_profit_pct int not null default 100,
  max_loss_pct int not null default 50,
  platform_fee_pct int not null default 1,
  one_trade_per_user boolean not null default true,
  paused boolean not null default false,
  updated_at timestamptz not null default now()
);
insert into public.risk_params (id) values (1) on conflict (id) do nothing;