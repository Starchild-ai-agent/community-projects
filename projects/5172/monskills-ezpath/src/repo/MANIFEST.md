# EZ-Path Agent Discovery & Integration Guide

This guide explains how agents discover and integrate the EZ-Path MONSKILLS skill.

## Agent Discovery

### Via Coinbase Bazaar / MONSKILLS Marketplace

Agents can discover this skill through:

1. **MONSKILLS Marketplace**: `npx skills add @infiniteezverse/monskills-ezpath`
2. **Community Dashboard**: https://community.iamstarchild.com/5172-monskills-ezpath
3. **AgentX Network**: Auto-discovered via AgentX release announcements

### Discovery Files

The following files enable auto-discovery:

- **`/.well-known/agent.json`** — Agent manifest with capabilities, pricing, chains, and integration metadata
- **`/.well-known/openapi.json`** — OpenAPI schema for RESTful clients and AI agent tooling
- **`/README.md`** — Human-readable documentation and quick-start guide

## Integration Methods

### Method 1: Direct NPM Installation (Recommended)

```bash
npm install @infiniteezverse/monskills-ezpath
```

Then in your agent code:

```typescript
import { getPrice, getQuote, batchQuotes } from '@infiniteezverse/monskills-ezpath';

const price = await getPrice(
  'base',
  '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // USDC
  '0x4200000000000000000000000000000000000006', // WETH
  '1000000' // 1 USDC
);
```

### Method 2: MONSKILLS Skill System

```bash
npx skills add @infiniteezverse/monskills-ezpath
```

Automatically registers skill handlers:

```typescript
// Skill is now available as a registered handler
const { getQuote, getPrice, batchQuotes } = require('@infiniteezverse/monskills-ezpath').skill.handlers;
```

### Method 3: GitHub Direct

```bash
npm install github:infiniteezverse/monskills-ezpath
```

## What Agents Can Use

### Function: `getPrice(chain, sellToken, buyToken, amount)`

Quick price lookup for single pair.

**Parameters:**
- `chain` (string): `'base'` | `'monad'`
- `sellToken` (address): ERC-20 token to sell
- `buyToken` (address): ERC-20 token to buy
- `amount` (string): Atomic units

**Returns:**
```typescript
{
  price: string;        // Human-readable price
  sources: string[];    // Venue names used
} | {
  error: string;        // Error message
}
```

### Function: `getQuote(request)`

Full quote with all venue details and settlement.

**Parameters:**
```typescript
{
  chain: 'base' | 'monad';
  sellToken: string;              // Address
  buyToken: string;               // Address
  sellAmount: string;             // Atomic units
  slippagePercentage?: number;    // Optional
}
```

**Returns:**
```typescript
{
  success: boolean;
  data?: {
    status: 'ok' | 'payment_required' | 'error';
    request_id: string;
    sellToken: string;
    buyToken: string;
    sellAmount: string;
    buyAmount: string;
    price: string;
    sources: Array<{
      name: string;       // Venue name
      buyAmount: string;
    }>;
    routingEngine: string;        // Best venue
    tier: 'basic' | 'resilient' | 'institutional';
    settlement_tx?: string;       // If executed on-chain
  };
  error?: string;
  paymentRequired?: boolean;      // If 402 Payment Required
  estimatedFee?: {
    usd: number;
    atomic: string;
    token: 'USDC';
  };
}
```

### Function: `batchQuotes(requests)`

Parallel quotes for multiple token pairs.

**Parameters:**
```typescript
EZPathQuoteRequest[]  // Array of quote requests
```

**Returns:**
```typescript
Promise<QuoteResult[]>  // Array of quote results
```

## Pricing & Payment

### Free Tier (Basic)

- Cost: **$0.03 USDC per quote**
- Venues: Direct 0x routing
- Rate limit: 120 requests/minute
- Payment: X402 EIP-3009 on Base USDC

### Resilient Tier

- Cost: **$0.10 USDC per quote**
- Venues: 4-venue racing
- Rate limit: 500 requests/minute

### Institutional Tier

- Cost: **$0.50 USDC per quote**
- Venues: Full 10-venue racing
- Rate limit: 1000 requests/minute

### Payment via X402 EIP-3009

The endpoint returns HTTP 402 when payment is required:

```typescript
const result = await getQuote(request);

if (result.paymentRequired) {
  // Agent must sign EIP-3009 TransferWithAuthorization
  // See X402 implementation in solver for details
  const signature = await signX402Payment(result.estimatedFee.atomic);
  const retryResult = await getQuoteWithPayment(request, signature);
}
```

## Use Cases

### 1. Agent Token Swaps

```typescript
// Agent wants to swap tokens with optimal routing
const quote = await getQuote({
  chain: 'base',
  sellToken: agentPortfolio.USDC,
  buyToken: agentPortfolio.WETH,
  sellAmount: swapAmount,
});

if (quote.success) {
  // Execute swap using quote.data.buyAmount as minimum output
  await executeSwap(quote.data);
}
```

### 2. Portfolio Valuation

```typescript
// Agent needs real-time portfolio value
const tokens = [USDC, WETH, AERO, USDbC];

const quotes = await batchQuotes(
  tokens.map(token => ({
    chain: 'base',
    sellToken: token.address,
    buyToken: USDC,
    sellAmount: token.balance,
  }))
);

const totalValue = quotes.reduce((sum, q) => 
  sum + BigInt(q.data?.buyAmount || 0), 0n
);
```

### 3. Arena Bankroll Management

```typescript
// Arena agent tracks stake value in real-time
const bankrollValue = await getPrice(
  'base',
  agentStakeToken,
  USDC,
  agentStakeAmount
);

const riskOfRuin = calculateRiskOfRuin(
  parseInt(bankrollValue.price) / 1e6
);

if (riskOfRuin > 0.7) {
  agentStrategy = 'conservative';
}
```

### 4. Arbitrage Detection

```typescript
// Agent monitors arbitrage opportunities
const baseQuote = await getPrice('base', TOKEN_A, TOKEN_B, '1000000');
const monadQuote = await getPrice('monad', TOKEN_A, TOKEN_B, '1000000');

const arbitrage = 
  parseFloat(monadQuote.price) - parseFloat(baseQuote.price);

if (arbitrage > 0.01) {
  // Opportunity detected: buy on Base, sell on Monad
}
```

## Supported Chains

### Live Now

| Chain | Status | Venues |
|-------|--------|--------|
| Base | ✅ Live | All 10 |
| Monad | ✅ Live | All 10 |

### Coming Soon

| Chain | Status |
|-------|--------|
| Arbitrum | 🚧 Q2 2026 |
| Optimism | 🚧 Q2 2026 |
| Polygon | 🚧 Q2 2026 |

## Error Handling

### Common Errors

```typescript
// Missing required parameters
{
  success: false,
  error: "Missing required parameters: sellToken, buyToken, sellAmount"
}

// Payment required (402)
{
  success: false,
  paymentRequired: true,
  estimatedFee: { usd: 0.03, atomic: "30000", token: "USDC" },
  error: "Payment required: $0.03 USDC via X402 EIP-3009"
}

// Network error
{
  success: false,
  error: "Request failed: Network timeout"
}
```

### Resilience Patterns

```typescript
// Retry with exponential backoff
async function getQuoteWithRetry(request, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const result = await getQuote(request);
      if (result.success) return result;
      
      // Exponential backoff
      await sleep(Math.pow(2, i) * 1000);
    } catch (err) {
      if (i === maxRetries - 1) throw err;
    }
  }
}

// Handle payment required gracefully
async function getQuoteWithPayment(request) {
  let result = await getQuote(request);
  
  if (result.paymentRequired) {
    const signature = await agent.signEIP3009(result.estimatedFee);
    result = await getQuote(request, { 'X-Payment': signature });
  }
  
  return result;
}
```

## Examples

See `/examples/` directory for complete working examples:

1. **`agent-usage.ts`** — Basic integration patterns
2. **`portfolio-valuation.ts`** — Real-time portfolio pricing
3. **`arena-agent.ts`** — Arena competition bankroll management

## Testing

```bash
npm install  # Install dependencies
npm test     # Run 18 unit tests
npm run test:watch  # Watch mode for TDD
```

## Support & Links

- 📖 Documentation: https://github.com/infiniteezverse/monskills-ezpath#readme
- 💬 Discord: https://discord.gg/monad
- 🐦 Twitter: https://twitter.com/infiniteezverse
- 📦 NPM: https://www.npmjs.com/package/@infiniteezverse/monskills-ezpath
- 🌐 EZ-Path: https://ezpath.myezverse.xyz
- 📋 OpenAPI: https://ezpath.myezverse.xyz/openapi.json
- 🤖 Agent Manifest: https://raw.githubusercontent.com/infiniteezverse/monskills-ezpath/main/.well-known/agent.json

## License

MIT — Free to use, modify, and redistribute.
