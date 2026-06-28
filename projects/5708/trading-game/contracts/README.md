# Contract deploy

## Layout
- `contracts/TradingGame.sol` — main settlement contract
- `test/TradingGame.t.sol` — Foundry unit tests
- `scripts/deploy.ts` — Hardhat deploy + pair config + ABI generation
- `scripts/gen-oracle-key.ts` — generate a dev oracle signer keypair

## Quick start

```bash
cd contracts
npm install

# 1. Generate a dev oracle signer
npx hardhat run scripts/gen-oracle-key.ts

# 2. Fill in web/.env.local (see web/.env.example)
#    MARGIN_TOKEN_ADDRESS, ORACLE_SIGNER_ADDRESS, ORACLE_PRIVATE_KEY,
#    DEPLOYER_PRIVATE_KEY, NEXT_PUBLIC_RPC_URL

# 3. Deploy
npx hardhat run scripts/deploy.ts --network sepolia

# 4. Verify on Etherscan
npx hardhat verify --network sepolia <ADDR> "<TOKEN>" "<ORACLE>" "<FEE>"
```

## Tests (Foundry)

```bash
forge install
forge test -vvv
```

## Security notes

- Contract NEVER trusts frontend price. openTrade + closeTrade require oracle sig.
- Close payloads carry a nonce burned on use -> replay-proof.
- PnL capped in-contract: profit <= +100% of margin, loss >= -50% of margin.
- deposit/withdraw use SafeERC20 + ReentrancyGuard. Trading pausable by owner.
