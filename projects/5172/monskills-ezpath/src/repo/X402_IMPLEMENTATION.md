# X402 EIP-3009 Payment Implementation

Complete implementation of X402 payment protocol for EZ-Path quote settlement using EIP-3009 TransferWithAuthorization.

## Overview

X402 is an HTTP protocol for micro-payments that enables agents to pay for on-demand services. EZ-Path uses X402 with EIP-3009 to handle payment for DEX routing quotes.

**Flow:**
```
Agent Request
    ↓
GET /api/v1/quote (no auth)
    ↓
HTTP 402 Payment Required (with fee details)
    ↓
Create EIP-3009 TransferWithAuthorization message
    ↓
Sign with agent's private key
    ↓
Build X-Payment header (base64 encoded)
    ↓
GET /api/v1/quote + X-Payment header
    ↓
HTTP 200 OK (with settlement_tx)
    ↓
Quote + settlement transaction ready
```

## Architecture

### Module Structure

```
src/payments/
├── eip3009.ts              # EIP-3009 signing and USDC domain
├── quote-execution.ts       # Quote executor with X402 retry logic
└── index.ts                 # Barrel export
```

### Key Components

#### 1. EIP-3009 Message Creation (`eip3009.ts`)

```typescript
// Create authorization message
const authMessage = createAuthorizationMessage(
  agentAddress,              // Who is paying
  TOLL_ADDRESS,             // Who receives payment
  BigInt(30000),            // Amount (atomic USDC)
  300                       // Validity (seconds)
);

// Result:
{
  from: '0x...',            // Agent address
  to: '0x13dD...',          // EZ-Path toll address
  value: '30000',           // 0.03 USDC
  validAfter: 0,            // Valid immediately
  validBefore: 1234567890,  // Expires in 5 minutes
  nonce: '0x...'            // Random 32 bytes
}
```

#### 2. EIP-712 Signing (`eip3009.ts`)

Messages are signed using EIP-712 typed data:

```typescript
const signature = await signer.signTypedData(
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
  authMessage
);
```

#### 3. X402 Payment Header (`eip3009.ts`)

The signature and message are packaged into an HTTP header:

```typescript
const header = createX402PaymentHeader({
  signature,            // EIP-712 signature
  authorization: authMessage,
  quote_issued_at: now,
});

// Header is base64-encoded JSON:
// X-Payment: eyJwYXlsb2FkIjp7InNpZ25hdHVyZSI6IjB4Li4uIn19
```

#### 4. Quote Execution (`quote-execution.ts`)

The `QuoteExecutor` class handles the complete flow:

```typescript
const executor = new QuoteExecutor(
  'https://ezpath.myezverse.xyz',
  {
    agentAddress: '0x...',
    signingFunction: async (message) => {
      return await signer.signTypedData(...);
    },
  }
);

const result = await executor.executeQuote({
  chain: 'base',
  sellToken: USDC,
  buyToken: WETH,
  sellAmount: '1000000',
});

if (result.success) {
  console.log('Bought:', result.data.buyAmount);
  console.log('Settlement:', result.data.settlement_tx);
} else if (result.paymentRequired) {
  console.log('Payment needed:', result.estimatedFee.usd, 'USDC');
}
```

## Integration Guide

### 1. Setup with ethers.js

```typescript
import { ethers } from 'ethers';
import { QuoteExecutor } from '@infiniteezverse/monskills-ezpath/dist/payments';

// Create signer
const privateKey = process.env.AGENT_PRIVATE_KEY;
const signer = new ethers.Wallet(privateKey);

// Create executor
const executor = new QuoteExecutor('https://ezpath.myezverse.xyz', {
  agentAddress: signer.address,
  signingFunction: async (message) => {
    return await signer.signTypedData(
      USDC_BASE_DOMAIN,
      TRANSFER_WITH_AUTHORIZATION_TYPE,
      message
    );
  },
});
```

### 2. Execute Quote with Payment

```typescript
// Get quote with automatic payment handling
const result = await executor.executeQuote({
  chain: 'base',
  sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
  buyToken: '0x4200000000000000000000000000000000000006',
  sellAmount: '1000000',
  slippagePercentage: 0.5,
});

// Handle result
if (result.success) {
  // Quote executed successfully
  console.log(`Bought: ${result.data.buyAmount} WETH`);
  console.log(`Best venue: ${result.data.routingEngine}`);
  
  // Settlement transaction is available
  if (result.data.settlement_tx) {
    await verifySettlementOnChain(result.data.settlement_tx);
  }
} else if (result.paymentRequired) {
  // Payment was required but failed
  console.log(`Payment failed: ${result.error}`);
  console.log(`Fee: ${result.estimatedFee.usd} USDC`);
  console.log(`Retries: ${result.retries}`);
} else {
  // Other error
  console.log(`Error: ${result.error}`);
}
```

### 3. With Arena Agent

```typescript
import { Agent } from '@infiniteezverse/monskills-ezpath/dist/agents';
import { QuoteExecutor } from '@infiniteezverse/monskills-ezpath/dist/payments';

// Create agent
const agent = new Agent({
  // ... agent config
});

// Create executor with agent's signer
const executor = new QuoteExecutor('https://ezpath.myezverse.xyz', {
  agentAddress: agent.address,
  signingFunction: agent.signer.signTypedData.bind(agent.signer),
});

// Get quotes for bankroll valuation
const quote = await executor.executeQuote({
  chain: 'base',
  sellToken: agent.bankrollToken,
  buyToken: USDC,
  sellAmount: agent.currentBankroll.toString(),
});

if (quote.success) {
  const bankrollValue = quote.data.buyAmount;
  // Use for risk calculations
}
```

## Payment Tiers

### Free Tier (Basic)
- **Cost:** $0.03 USDC
- **Amount:** 30,000 atomic USDC
- **Features:** Direct 0x routing
- **Rate limit:** 120 requests/minute

### Resilient Tier
- **Cost:** $0.10 USDC
- **Amount:** 100,000 atomic USDC
- **Features:** 4-venue racing
- **Rate limit:** 500 requests/minute

### Institutional Tier
- **Cost:** $0.50 USDC
- **Amount:** 500,000 atomic USDC
- **Features:** Full 10-venue racing
- **Rate limit:** 1000 requests/minute

### Selecting Tier

```typescript
import { getTierByAmount, PAYMENT_TIERS } from '@infiniteezverse/monskills-ezpath/dist/payments';

// Get tier by amount
const tier = getTierByAmount(BigInt(30000));  // 'basic'
const tier = getTierByAmount(BigInt(100000)); // 'resilient'
const tier = getTierByAmount(BigInt(500000)); // 'institutional'

// Get tier config
const basicTier = PAYMENT_TIERS.basic;
console.log(`Cost: $${basicTier.costUSDC}`);
console.log(`Atomic: ${basicTier.costAtomic.toString()}`);
console.log(`Features: ${basicTier.description}`);
```

## Error Handling

### HTTP 402 Payment Required

When the endpoint requires payment, it returns HTTP 402 with fee details:

```typescript
// Handle 402 response
if (result.paymentRequired) {
  console.log(`Payment required: ${result.error}`);
  console.log(`Fee: ${result.estimatedFee.usd} USDC`);
  console.log(`Atomic: ${result.estimatedFee.atomic}`);
  
  // Agent can:
  // 1. Sign and retry (automatic in QuoteExecutor)
  // 2. Cancel the operation
  // 3. Upgrade to paid tier
}
```

### Signing Failure

If the agent cannot sign the message:

```typescript
// Result includes error details
if (!result.success && result.paymentRequired) {
  if (result.error.includes('sign')) {
    console.log('Signing failed - check private key');
    console.log('Ensure signer has signing capability');
  }
}
```

### Expired Authorization

Authorization messages have a 5-minute validity window:

```typescript
// If message expires before broadcast:
const authMessage = createAuthorizationMessage(
  agentAddress,
  TOLL_ADDRESS,
  amount,
  300 // Increase validity if needed
);

// Validation will catch expired messages:
const validation = validateAuthorizationMessage(authMessage);
if (!validation.valid) {
  console.log(`Error: ${validation.error}`);
  // Create new message and retry
}
```

## Security Considerations

### Private Key Management

```typescript
// ✅ Good: Load from secure environment variable
const privateKey = process.env.AGENT_PRIVATE_KEY;
const signer = new ethers.Wallet(privateKey);

// ❌ Bad: Hardcoded private key
const signer = new ethers.Wallet('0x123...');

// ✅ Better: Use secrets manager
const privateKey = await secretsManager.getSecret('AGENT_PRIVATE_KEY');
const signer = new ethers.Wallet(privateKey);
```

### Nonce Randomness

Each authorization message must have a random nonce to prevent replay attacks:

```typescript
// createAuthorizationMessage uses crypto.randomBytes(32)
// This is cryptographically secure

// Verify nonce uniqueness
const nonce = authMessage.nonce;
// Should verify nonce hasn't been used before
```

### Validity Window

Authorization is only valid during a specific time window:

```typescript
// Message created at 12:00:00
// validAfter: 0 (immediately)
// validBefore: 12:05:00 (5 minutes)

// If broadcast after 12:05:00: invalid
// EIP-3009 validation will reject it
```

### USDC Domain Verification

The domain separator must match the contract:

```typescript
// For USDC v2 on Base: 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
// Different address = different domain = invalid signature

// Always verify:
// - Correct USDC address
// - Correct chain ID (8453 for Base)
// - Correct contract version (v2)
```

## Troubleshooting

### "Payment signature is invalid"

**Cause:** Signature was computed with wrong domain or message

**Solution:**
```typescript
// Verify domain matches USDC
console.log(USDC_BASE_DOMAIN.verifyingContract);
// Should be: 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913

// Verify chain ID
console.log(USDC_BASE_DOMAIN.chainId);
// Should be: 8453 (Base)

// Re-sign with correct domain:
const signature = await signer.signTypedData(
  USDC_BASE_DOMAIN,
  TRANSFER_WITH_AUTHORIZATION_TYPE,
  message
);
```

### "Authorization expired"

**Cause:** Message validBefore has passed

**Solution:**
```typescript
// Create new message with longer validity
const message = createAuthorizationMessage(
  from,
  to,
  amount,
  600  // 10 minutes instead of 5
);

// Or check system time is correct:
console.log('Current time:', Date.now());
console.log('Valid before:', message.validBefore * 1000);
```

### "Invalid nonce"

**Cause:** Nonce is not 32 random bytes

**Solution:**
```typescript
// Nonce must be exactly 66 characters: 0x + 64 hex chars
const nonce = message.nonce;
console.log(`Length: ${nonce.length}`); // Should be 66
console.log(`Prefix: ${nonce.substring(0, 2)}`); // Should be 0x
```

## Production Checklist

- [ ] Private key loaded from secure source (not hardcoded)
- [ ] USDC domain verified (0x8335... on Base)
- [ ] Chain ID correct (8453 for Base)
- [ ] Signer has sufficient USDC balance for payment
- [ ] Error handling implemented for all failure cases
- [ ] Logging/monitoring for payment failures
- [ ] Rate limiting respected (120/minute for basic tier)
- [ ] Validity window set appropriately (300s minimum)
- [ ] Nonce is random for each message
- [ ] Settlement transaction verified on-chain

## Examples

Complete working examples in `/examples/`:

- **`x402-payment.ts`** — Full X402 payment flow with 8 examples

Run examples:

```bash
npm install
npx ts-node examples/x402-payment.ts
```

## References

- **EIP-3009:** https://eips.ethereum.org/EIPS/eip-3009
- **EIP-712:** https://eips.ethereum.org/EIPS/eip-712
- **X402 Spec:** https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/402
- **USDC Docs:** https://www.circle.com/en/usdc
- **Ethers.js:** https://docs.ethers.org/v6/

## Support

- 📖 Code: https://github.com/infiniteezverse/monskills-ezpath/src/payments/
- 💬 Discord: https://discord.gg/monad
- 🐦 Twitter: @infiniteezverse
- 🌐 EZ-Path: https://ezpath.myezverse.xyz
