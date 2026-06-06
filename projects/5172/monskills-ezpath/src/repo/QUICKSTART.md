# 🚀 Quick Start Guide

Get up and running with EZ-Path MONSKILLS in 5 minutes.

---

## Installation

### Option 1: NPM (Recommended)
```bash
npm install @infiniteezverse/monskills-ezpath
```

### Option 2: MONSKILLS Skill Manager
```bash
npx skills add @infiniteezverse/monskills-ezpath
```

### Option 3: GitHub Direct
```bash
npm install github:infiniteezverse/monskills-ezpath
```

---

## 1️⃣ Get a Price Quote (30 seconds)

```typescript
import { getPrice } from '@infiniteezverse/monskills-ezpath';

// Get WETH/USDC price on Base
const result = await getPrice(
  'base',
  '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // USDC
  '0x4200000000000000000000000000000000000006', // WETH
  '1000000' // 1 USDC
);

if ('price' in result) {
  console.log(`Price: ${result.price} WETH`);
  console.log(`Venues: ${result.sources.join(', ')}`);
} else {
  console.log(`Error: ${result.error}`);
}
```

**Output:**
```
Price: 0.000503 WETH
Venues: 0x, Uniswap V3, Curve
```

---

## 2️⃣ Get Full Quote with All Venues (1 minute)

```typescript
import { getQuote } from '@infiniteezverse/monskills-ezpath';

const quote = await getQuote({
  chain: 'base',
  sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
  buyToken: '0x4200000000000000000000000000000000000006',
  sellAmount: '1000000',
  slippagePercentage: 0.5,
});

if (quote.success && quote.data) {
  console.log(`Best price: ${quote.data.price}`);
  console.log(`Best venue: ${quote.data.routingEngine}`);
  console.log(`All venues: ${quote.data.sources.length}`);
  
  quote.data.sources.forEach(venue => {
    console.log(`  ${venue.name}: ${venue.buyAmount}`);
  });
} else if (quote.paymentRequired) {
  console.log(`Payment required: $${quote.estimatedFee?.usd} USDC`);
} else {
  console.log(`Error: ${quote.error}`);
}
```

---

## 3️⃣ Portfolio Valuation (2 minutes)

```typescript
import { batchQuotes } from '@infiniteezverse/monskills-ezpath';

// Value multiple tokens at once
const requests = [
  {
    chain: 'base',
    sellToken: '0x4200000000000000000000000000000000000006', // WETH
    buyToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // USDC
    sellAmount: '1000000000000000000', // 1 WETH (18 decimals)
  },
  {
    chain: 'base',
    sellToken: '0x50c5725949A6F0c72EC20E08a6DE0146F30F1F75', // USDbC
    buyToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // USDC
    sellAmount: '1000000', // 1 USDbC (6 decimals)
  },
];

const results = await batchQuotes(requests);

let totalValue = 0n;
results.forEach((result, index) => {
  if (result.success && result.data) {
    const value = BigInt(result.data.buyAmount);
    totalValue += value;
    console.log(`Token ${index + 1}: $${Number(value) / 1e6} USDC`);
  }
});

console.log(`Total: $${Number(totalValue) / 1e6} USDC`);
```

---

## 4️⃣ Create Arena Agent (3 minutes)

```typescript
import { Agent } from '@infiniteezverse/monskills-ezpath/dist/agents';

// Create agent
const agent = new Agent({
  id: 'my-agent-001',
  name: 'MyAgent',
  address: '0x1234567890123456789012345678901234567890',
  chain: 'monad',
  bankrollToken: '0x4200000000000000000000000000000000000006', // WETH
  initialBankroll: BigInt('10000000000000000000'), // 10 WETH
  minimumBankroll: BigInt('500000000000000000'), // 0.5 WETH
  skillLevel: 'advanced',
  strategy: 'balanced',
});

// Check status
const status = await agent.getStatus();
console.log(`Bankroll: ${status.bankroll.inUSDC} USDC`);
console.log(`Health: ${status.risk.healthScore}/100`);
console.log(`Strategy: ${status.strategy.recommended}`);
```

---

## 5️⃣ X402 Payment Execution (4 minutes)

```typescript
import { QuoteExecutor } from '@infiniteezverse/monskills-ezpath/dist/payments';
import { ethers } from 'ethers';

// Setup signer
const signer = new ethers.Wallet(process.env.AGENT_PRIVATE_KEY);

// Create executor
const executor = new QuoteExecutor('https://ezpath.myezverse.xyz', {
  agentAddress: signer.address,
  signingFunction: async (message) => {
    return await signer.signTypedData(
      {
        name: 'USD Coin',
        version: '2',
        chainId: 8453,
        verifyingContract: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
      },
      {
        TransferWithAuthorization: [
          { name: 'from', type: 'address' },
          { name: 'to', type: 'address' },
          { name: 'value', type: 'uint256' },
          { name: 'validAfter', type: 'uint256' },
          { name: 'validBefore', type: 'uint256' },
          { name: 'nonce', type: 'bytes32' },
        ],
      },
      message
    );
  },
});

// Execute quote with automatic payment
const result = await executor.executeQuote({
  chain: 'base',
  sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
  buyToken: '0x4200000000000000000000000000000000000006',
  sellAmount: '1000000',
});

if (result.success) {
  console.log(`Quote: ${result.data?.price}`);
  console.log(`Settlement: ${result.data?.settlement_tx}`);
} else {
  console.log(`Failed: ${result.error}`);
}
```

---

## Chains

### Live Now ✅
- **Base** (0x4200000000000000000000000000000000000006 = WETH)
- **Monad** (same token addresses)

### Coming Soon 🚧
- Arbitrum
- Optimism
- Polygon

---

## Common Tasks

### 1. Check Agent Status
```typescript
const status = await agent.getStatus();
console.log(JSON.stringify(status, null, 2));
```

### 2. Join Tournament
```typescript
const joined = await agent.joinTournament(tournament, buyinAmount);
if (joined) console.log('Joined!');
```

### 3. Get Strategy Recommendation
```typescript
const strategy = await agent.getStrategyRecommendation();
console.log(`Recommended: ${strategy.recommendedStrategy}`);
```

### 4. Value Bankroll
```typescript
const metrics = await agent.getMetrics();
console.log(`Bankroll: ${metrics.valueInUSDC} USDC`);
console.log(`Buyins: ${metrics.buyinsRemaining}`);
console.log(`Risk: ${(metrics.riskOfRuin * 100).toFixed(1)}%`);
```

---

## API Reference

### getPrice(chain, sellToken, buyToken, amount)
**Quick price lookup**
- Returns: `{price, sources}` or `{error}`
- Use for: Fast quotes without venue details

### getQuote(request)
**Full quote with all venues**
- Returns: `{success, data, error, paymentRequired}`
- Use for: Detailed quotes with settlement_tx

### batchQuotes(requests)
**Multiple quotes in parallel**
- Returns: `QuoteResult[]`
- Use for: Portfolio valuation, multiple pairs

### Agent (class)
**Tournament competition agent**
- Methods: `joinTournament()`, `getStatus()`, `getStrategyRecommendation()`, `getMetrics()`
- Use for: Arena competition, bankroll management

### QuoteExecutor (class)
**X402 payment-enabled quote execution**
- Methods: `executeQuote()`
- Use for: Quotes requiring payment, settlement execution

---

## Error Handling

```typescript
const result = await getQuote(request);

if (result.paymentRequired) {
  // Quote requires payment (402 response)
  console.log(`Pay: ${result.estimatedFee?.usd} USDC`);
} else if (result.success) {
  // Quote successful
  console.log(`Price: ${result.data?.price}`);
} else {
  // Error
  console.log(`Error: ${result.error}`);
}
```

---

## Monad Optimization

If running on **Monad**, you get:
- ✅ 3x faster quotes (0.7s block time)
- ✅ Real-time monitoring (every block)
- ✅ High-frequency trading ready (10,000 TPS)

```typescript
import { MONAD_CONFIG } from '@infiniteezverse/monskills-ezpath/dist/config/monad';

// Use Monad RPC
const rpc = await getMonadRPC();

// Monad-specific venues
const venues = MONAD_CONFIG.venues;
console.log(`Aerodrome priority: ${venues.aerodrome.priority}`);
```

---

## Examples

Run complete working examples:

```bash
# Basic usage
npx ts-node examples/agent-usage.ts

# Arena tournament
npx ts-node examples/arena-agent-template.ts

# Portfolio valuation
npx ts-node examples/portfolio-valuation.ts

# Monad optimization
npx ts-node examples/monad-agent.ts

# X402 payments
npx ts-node examples/x402-payment.ts
```

---

## Full Documentation

- **Installation & Integration:** [MANIFEST.md](MANIFEST.md)
- **Monad-specific features:** [MONAD.md](MONAD.md)
- **Arena agent framework:** [ARENA.md](ARENA.md)
- **X402 payment implementation:** [X402_IMPLEMENTATION.md](X402_IMPLEMENTATION.md)
- **Deployment guide:** [DEPLOYMENT.md](DEPLOYMENT.md)

---

## Troubleshooting

### "Cannot find module '@infiniteezverse/monskills-ezpath'"
```bash
# Make sure you installed it
npm install @infiniteezverse/monskills-ezpath

# Or use directly from GitHub
npm install github:infiniteezverse/monskills-ezpath
```

### "Payment signature invalid"
- Check your private key is correct
- Verify agent address matches signer
- Ensure USDC domain is correct (0x8335... on Base)

### "Quote timeout"
- Increase timeout in executor options
- Check network connectivity
- Try fallback RPC endpoint

---

## Support

- 📖 Documentation: https://github.com/infiniteezverse/monskills-ezpath
- 💬 Discord: https://discord.gg/monad
- 🐦 Twitter: @infiniteezverse
- 🐛 Issues: https://github.com/infiniteezverse/monskills-ezpath/issues

---

**You're ready! Start building agents on Monad! 🚀**
