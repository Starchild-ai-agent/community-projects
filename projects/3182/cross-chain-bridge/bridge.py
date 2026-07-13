#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cross-chain bridge via LiFi + Starchild Agent Wallet (gas-sponsored).

One-shot: quote → check allowance → approve if needed → execute → poll destination.

Usage:
  python3 scripts/bridge.py --amount 5 --from arbitrum --to base --token USDC
  python3 scripts/bridge.py --amount 10 --from arbitrum --to base --token USDC --slippage 1
  python3 scripts/bridge.py --info   # show supported chains/tokens

Cost: ~$0.015 bridge fee + 1 LLM call (this script) ≈ <$0.05 total.
"""

import argparse
import json
import sys
import time

from core.http_client import proxied_get, proxied_post
from core.skill_tools import wallet

# ── Constants ─────────────────────────────────────────────────────────────────

WALLET = "0x3a81f1Fb069107fdaAF0a6598d46A0B0e3612973"
LIFI_ROUTER = "0x1231DEB6f5749EF6cE6943a275A1D3E7486F4EaE"  # same on all EVM chains
CALLER = "chat:3182"

# Chain name → chain id + RPC
CHAINS = {
    "arbitrum":  {"id": 42161,  "rpc": "https://arb1.arbitrum.io/rpc"},
    "base":      {"id": 8453,   "rpc": "https://mainnet.base.org"},
    "ethereum":  {"id": 1,      "rpc": "https://eth.llamarpc.com"},
    "optimism":  {"id": 10,     "rpc": "https://mainnet.optimism.io"},
    "polygon":   {"id": 137,    "rpc": "https://polygon-rpc.com"},
    "bsc":       {"id": 56,     "rpc": "https://bsc-dataseed.binance.org"},
}

# Token addresses per chain (6 decimals for USDC/USDT)
TOKENS = {
    "USDC": {
        "arbitrum": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
        "base":     "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "ethereum": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "optimism": "0x0b2C639c533813f4Aa9D7837CAf62453D4967562",
        "polygon":  "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
        "bsc":      "0x8AC76A51cd9C9779E45cDf3F0e6E3A779c61c3D3",
    },
    "USDT": {
        "arbitrum": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FcBB9",
        "ethereum": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "polygon":  "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
        "bsc":      "0x55d398326f99059fF775485246999027B3197955",
    },
}

DECIMALS = {"USDC": 6, "USDT": 6}

# ERC-20 selectors
SEL_ALLOWANCE  = "0xdd62ed3e"  # allowance(address,address)
SEL_BALANCEOF   = "0x70a08231"  # balanceOf(address)
SEL_APPROVE     = "0x095ea7b3"  # approve(address,uint256)


# ── Helpers ──────────────────────────────────────────────────────────────────

def pad32(addr: str) -> str:
    """Pad a 20-byte address to 32 bytes (left-padded) for calldata encoding."""
    return addr[2:].lower().zfill(64)


def to_hex(amount: int) -> str:
    return hex(amount)[2:].zfill(64)


def rpc_call(rpc: str, to: str, data: str) -> str:
    """Read-only eth_call to a contract."""
    payload = {
        "jsonrpc": "2.0", "id": 1, "method": "eth_call",
        "params": [{"to": to, "data": data}, "latest"],
    }
    r = proxied_post(rpc, json=payload,
                     headers={"SC-CALLER-ID": CALLER, "Content-Type": "application/json"},
                     timeout=15)
    result = r.json()
    if "error" in result:
        raise RuntimeError(f"RPC error: {result['error']}")
    return result.get("result", "0x0")


def get_allowance(chain: str, token: str) -> int:
    """Check how much `token` the LiFi router is allowed to spend from our wallet."""
    rpc = CHAINS[chain]["rpc"]
    token_addr = TOKENS[token][chain]
    data = SEL_ALLOWANCE + pad32(WALLET) + pad32(LIFI_ROUTER)
    raw = rpc_call(rpc, token_addr, data)
    return int(raw, 16) if raw and raw != "0x" else 0


def get_balance(chain: str, token: str) -> int:
    """Get raw token balance (in minimal units)."""
    rpc = CHAINS[chain]["rpc"]
    token_addr = TOKENS[token][chain]
    data = SEL_BALANCEOF + pad32(WALLET)
    raw = rpc_call(rpc, token_addr, data)
    return int(raw, 16) if raw and raw != "0x" else 0


def lifi_quote(from_chain: str, to_chain: str, token: str, amount_raw: int, slippage_pct: float):
    """Get a LiFi cross-chain quote. Returns the full quote dict."""
    params = {
        "fromChain": str(CHAINS[from_chain]["id"]),
        "toChain": str(CHAINS[to_chain]["id"]),
        "fromToken": TOKENS[token][from_chain],
        "toToken": TOKENS[token][to_chain],
        "fromAmount": str(amount_raw),
        "fromAddress": WALLET,
        "slippage": slippage_pct / 100,
    }
    r = proxied_get("https://li.quest/v1/quote", params=params,
                    headers={"SC-CALLER-ID": CALLER}, timeout=30)
    data = r.json()
    if "transactionRequest" not in data:
        raise RuntimeError(f"LiFi quote failed: {json.dumps(data)[:500]}")
    return data


def send_tx(to: str, data: str, chain_id: int) -> dict:
    """Broadcast a sponsored UserOperation via Starchild wallet."""
    return wallet.wallet_transfer(to=to, amount="0", chain_id=chain_id, data=data)


def wait_for_allowance(chain: str, token: str, expected: int, timeout: int = 30):
    """Poll until allowance reflects the approve tx."""
    rpc = CHAINS[chain]["rpc"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        if get_allowance(chain, token) >= expected:
            return True
        time.sleep(3)
    return False


def wait_for_balance_increase(chain: str, token: str, before: int, timeout: int = 180) -> int:
    """Poll destination balance until it increases. Returns new balance."""
    deadline = time.time() + timeout
    last = before
    while time.time() < deadline:
        now = get_balance(chain, token)
        if now > before:
            return now
        time.sleep(10)
    return last


# ── Main flow ────────────────────────────────────────────────────────────────

def run_bridge(amount: float, from_chain: str, to_chain: str, token: str, slippage: float):
    dec = DECIMALS[token]
    amount_raw = int(amount * (10 ** dec))

    print(f"{'='*60}")
    print(f"  Bridge: {amount} {token}  {from_chain} → {to_chain}")
    print(f"  Slippage: {slippage}%  | Wallet: {WALLET[:10]}...{WALLET[-6:]}")
    print(f"{'='*60}")

    # 1. Pre-flight: check source balance
    src_bal = get_balance(from_chain, token)
    src_human = src_bal / (10 ** dec)
    print(f"\n[1/6] Source balance ({from_chain}): {src_human} {token}")
    if src_bal < amount_raw:
        print(f"  ❌ Insufficient balance. Need {amount}, have {src_human}.")
        sys.exit(1)

    dst_before = get_balance(to_chain, token)
    print(f"      Destination balance ({to_chain}) before: {dst_before / (10**dec)} {token}")

    # 2. Get LiFi quote
    print(f"\n[2/6] Fetching LiFi quote (Across bridge)...")
    quote = lifi_quote(from_chain, to_chain, token, amount_raw, slippage)
    tr = quote["transactionRequest"]
    to_amount = int(quote["estimate"]["toAmount"]) / (10 ** dec)
    to_min = int(quote["estimate"]["toAmountMin"]) / (10 ** dec)
    est_fee = amount - to_amount
    print(f"  ✅ Route: {quote.get('tool', '?')} bridge")
    print(f"  ✅ You'll receive: ~{to_amount} {token} (min {to_min})")
    print(f"  ✅ Bridge fee: ~${est_fee:.4f} ({est_fee/amount*100:.2f}%)")
    print(f"  ✅ ETA: {quote['estimate'].get('executionDuration', '?')}s")

    # 3. Check allowance & approve if needed
    print(f"\n[3/6] Checking allowance for LiFi router...")
    allowance = get_allowance(from_chain, token)
    print(f"  Current allowance: {allowance / (10**dec)} {token}")

    if allowance < amount_raw:
        print(f"  ⚠️  Need approval. Sending approve tx...")
        approve_data = SEL_APPROVE + pad32(LIFI_ROUTER) + to_hex(amount_raw)
        approve_tx = send_tx(TOKENS[token][from_chain], approve_data, CHAINS[from_chain]["id"])
        approve_hash = approve_tx.get("data", {}).get("user_operation_hash", "")
        print(f"  ✅ Approve sent: {approve_hash[:18]}...")

        print(f"  Waiting for confirmation...", end=" ", flush=True)
        if wait_for_allowance(from_chain, token, amount_raw, timeout=30):
            print("confirmed ✅")
        else:
            print("timeout ⚠️ (continuing anyway)")
    else:
        print(f"  ✅ Sufficient allowance, skipping approve.")

    # 4. Re-quote (quote may be stale after approval wait)
    print(f"\n[4/6] Re-quoting (fresh price)...")
    quote = lifi_quote(from_chain, to_chain, token, amount_raw, slippage)
    tr = quote["transactionRequest"]
    to_amount = int(quote["estimate"]["toAmount"]) / (10 ** dec)
    print(f"  Fresh quote: ~{to_amount} {token}")

    # 5. Execute bridge
    print(f"\n[5/6] Broadcasting bridge tx via Starchild wallet (gas sponsored)...")
    result = send_tx(tr["to"], tr["data"], CHAINS[from_chain]["id"])
    bridge_hash = result.get("data", {}).get("user_operation_hash", "")
    tx_id = result.get("data", {}).get("transaction_id", "")
    print(f"  ✅ Bridge tx sent!")
    print(f"     user_operation_hash: {bridge_hash}")
    if tx_id:
        print(f"     transaction_id: {tx_id}")

    # 6. Poll destination for arrival
    print(f"\n[6/6] Waiting for funds on {to_chain} (polling every 10s, up to 3min)...")
    print(f"      Watching for balance increase above {dst_before / (10**dec)} {token}")
    new_bal = wait_for_balance_increase(to_chain, token, dst_before, timeout=180)
    received = (new_bal - dst_before) / (10 ** dec)

    if received > 0:
        print(f"\n{'='*60}")
        print(f"  ✅ BRIDGE COMPLETE")
        print(f"  Sent:    {amount} {token} on {from_chain}")
        print(f"  Received: {received:.6f} {token} on {to_chain}")
        print(f"  Net fee:  ${amount - received:.4f} ({(amount-received)/amount*100:.2f}%)")
        print(f"{'='*60}")
    else:
        print(f"\n  ⏳ Funds not yet arrived after 3min. Bridge may still be processing.")
        print(f"     Check: https://li.quest/v1/status?txHash={bridge_hash}")
        print(f"     Or check {to_chain} balance in a few minutes.")


def show_info():
    print(f"\n{'='*60}")
    print(f"  Bridge.py — Supported Chains & Tokens")
    print(f"{'='*60}")
    print(f"\nWallet: {WALLET}")
    print(f"\nChains:")
    for name, info in CHAINS.items():
        print(f"  {name:10} (id={info['id']})")
    print(f"\nTokens (by chain):")
    for token, chains in TOKENS.items():
        print(f"\n  {token} ({DECIMALS[token]} decimals):")
        for chain, addr in chains.items():
            print(f"    {chain:10} {addr}")
    print(f"\nLiFi router (all chains): {LIFI_ROUTER}")
    print(f"\nUsage:")
    print(f"  python3 scripts/bridge.py --amount 5 --from arbitrum --to base --token USDC")
    print(f"  python3 scripts/bridge.py --amount 10 --from arbitrum --to base --token USDC --slippage 1")
    print()


def main():
    p = argparse.ArgumentParser(description="Cross-chain bridge via LiFi + Starchild wallet")
    p.add_argument("--amount", type=float, help="Amount to bridge (e.g. 5)")
    p.add_argument("--from", dest="from_chain", default="arbitrum", help="Source chain")
    p.add_argument("--to", dest="to_chain", default="base", help="Destination chain")
    p.add_argument("--token", default="USDC", help="Token symbol (USDC/USDT)")
    p.add_argument("--slippage", type=float, default=0.5, help="Slippage %% (default 0.5)")
    p.add_argument("--info", action="store_true", help="Show supported chains/tokens and exit")
    args = p.parse_args()

    if args.info:
        show_info()
        return

    if not args.amount:
        print("Error: --amount is required. Use --info for help.")
        sys.exit(1)

    # Validate
    if args.from_chain not in CHAINS:
        print(f"Error: source chain '{args.from_chain}' not supported. Use --info.")
        sys.exit(1)
    if args.to_chain not in CHAINS:
        print(f"Error: destination chain '{args.to_chain}' not supported. Use --info.")
        sys.exit(1)
    if args.token not in TOKENS:
        print(f"Error: token '{args.token}' not supported. Use --info.")
        sys.exit(1)
    if args.token not in TOKENS or args.from_chain not in TOKENS.get(args.token, {}):
        print(f"Error: {args.token} not available on {args.from_chain}. Use --info.")
        sys.exit(1)
    if args.token not in TOKENS or args.to_chain not in TOKENS.get(args.token, {}):
        print(f"Error: {args.token} not available on {args.to_chain}. Use --info.")
        sys.exit(1)
    if args.from_chain == args.to_chain:
        print("Error: source and destination chains are the same.")
        sys.exit(1)

    try:
        run_bridge(args.amount, args.from_chain, args.to_chain, args.token, args.slippage)
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
