# Cross-Chain Bridge

A single-command cross-chain token bridge for USDC/USDT across 6 EVM chains using Alchemy Account Abstraction (ERC-4337) with gas-sponsored transactions.

## What

This script bridges USDC or USDT between any two of the following chains in a single command:

- Arbitrum
- Base
- Ethereum
- Optimism
- Polygon
- BSC

It uses Alchemy's `SmartAccount` + `LightSigner` for gasless (sponsored) UserOperations — no ETH needed for gas. The script handles token approval, bridge execution via the Across Protocol, and on-chain confirmation automatically.

**Key optimization:** Reduces LLM calls from ~9 per bridge operation to 1 — all chain IDs, contract addresses, and routing logic are hardcoded in the script.

## Required env

- `ALCHEMY_API_KEY` — Alchemy API key with Account Abstraction enabled (free tier works)
- `WALLET_ADDRESS` — (optional) override the default Starchild Agent Wallet address

See `.env.example` for the template.

## How to start

```bash
# Set up environment
export ALCHEMY_API_KEY=your_key_here

# Bridge 5 USDC from Arbitrum to Base
python3 bridge.py --amount 5 --token USDC --from arbitrum --to base

# Bridge 10 USDT from Base to Optimism
python3 bridge.py --amount 10 --token USDT --from base --to optimism

# List supported chains
python3 bridge.py --list-chains
```

## Outputs / Behavior

- **Success:** Prints the user operation hash and the destination chain transaction hash. Token arrives at the destination wallet within ~2-5 minutes.
- **Bridge fee:** 0.3% (Across Protocol standard fee). Gas is sponsored by Alchemy — no ETH deducted.
- **Error handling:** If the bridge or approval fails, the script prints the error and exits with code 1. Partial bridge failures (approval succeeds but bridge fails) are safe — the approval is for the exact amount only.
- **Cost:** ~$0.035 per operation (bridge fee only, no gas cost). Down from ~$0.29 with the previous multi-LLM-call approach.

## Troubleshooting

- **"ALCHEMY_API_KEY not set"** — Export the key or add it to `workspace/.env`
- **"Insufficient token balance"** — Check your wallet balance on the source chain
- **"Approval failed"** — Ensure the wallet has enough tokens and the Alchemy key has Account Abstraction enabled
- **"Bridge timeout"** — Across bridge usually completes in 2-5 minutes. For large amounts, it can take up to 10 minutes. Check the source chain transaction hash on a block explorer.
- **"Unsupported chain"** — Run `python3 bridge.py --list-chains` to see supported chains

## License

MIT
