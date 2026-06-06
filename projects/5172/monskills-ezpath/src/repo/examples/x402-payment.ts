/**
 * X402 EIP-3009 Payment Example
 * Complete flow: quote → 402 response → sign → retry → settlement
 *
 * This example shows:
 * 1. Creating authorization messages
 * 2. Signing with EIP-3009
 * 3. Building X402 payment headers
 * 4. Executing quotes with payment
 * 5. Handling settlement transactions
 */

import {
  createAuthorizationMessage,
  createX402PaymentHeader,
  parseX402PaymentHeader,
  validateAuthorizationMessage,
  getTierByAmount,
  PAYMENT_TIERS,
  TOLL_ADDRESS,
  X402_CONFIG,
} from '../src/payments/eip3009';
import { QuoteExecutor } from '../src/payments/quote-execution';
import type { TransferAuthorizationMessage } from '../src/payments/eip3009';

/**
 * Mock signing function
 * In production, use ethers.js Signer.signTypedData()
 *
 * @example
 * const signer = new ethers.Wallet(privateKey);
 * const signature = await signer.signTypedData(domain, types, message);
 */
async function mockSignMessage(message: TransferAuthorizationMessage): Promise<string> {
  // In production, this would be:
  // const signature = await signer.signTypedData(
  //   USDC_BASE_DOMAIN,
  //   TRANSFER_WITH_AUTHORIZATION_TYPE,
  //   message
  // );

  console.log('[Mock Signer] Would sign this message:');
  console.log(`  From: ${message.from}`);
  console.log(`  To: ${message.to}`);
  console.log(`  Value: ${message.value} USDC`);
  console.log(`  Nonce: ${message.nonce}`);
  console.log(`  Valid: ${message.validAfter} → ${message.validBefore}`);

  // Return a mock signature
  return '0x' + '0'.repeat(130); // 65 bytes (130 hex chars) for signature
}

/**
 * Example 1: Create Authorization Message
 */
async function createAuthorizationExample() {
  console.log('📝 Creating Authorization Message\n');

  const agentAddress = '0x1234567890123456789012345678901234567890';
  const paymentAmount = PAYMENT_TIERS.basic.costAtomic; // $0.03 USDC

  const authMessage = createAuthorizationMessage(
    agentAddress,
    TOLL_ADDRESS,
    paymentAmount,
    300 // 5 minute validity
  );

  console.log('Authorization Message:');
  console.log(`  From (payer): ${authMessage.from}`);
  console.log(`  To (toll): ${authMessage.to}`);
  console.log(`  Value: ${authMessage.value} atomic USDC`);
  console.log(`  Valid after: ${authMessage.validAfter}`);
  console.log(`  Valid before: ${authMessage.validBefore}`);
  console.log(`  Nonce: ${authMessage.nonce}`);
  console.log();

  // Validate message
  const validation = validateAuthorizationMessage(authMessage);
  console.log(`Validation: ${validation.valid ? '✅ VALID' : '❌ INVALID'}`);
  if (!validation.valid) {
    console.log(`  Error: ${validation.error}`);
  }
  console.log();

  return authMessage;
}

/**
 * Example 2: Sign Message with EIP-3009
 */
async function signMessageExample(message: TransferAuthorizationMessage) {
  console.log('🔐 Signing Message with EIP-3009\n');

  console.log('Signing context:');
  console.log(`  Domain: ${X402_CONFIG.chain} (Chain ID: ${X402_CONFIG.chainId})`);
  console.log(`  USDC: ${X402_CONFIG.usdcAddress}`);
  console.log(`  Type: TransferWithAuthorization (EIP-712)`);
  console.log();

  try {
    const signature = await mockSignMessage(message);

    console.log('Signature generated:');
    console.log(`  ${signature.substring(0, 20)}...${signature.substring(-20)}`);
    console.log(`  Length: ${signature.length} characters (${(signature.length - 2) / 2} bytes)`);
    console.log();

    return signature;
  } catch (error) {
    console.error('Signing failed:', error);
    return null;
  }
}

/**
 * Example 3: Create X402 Payment Header
 */
async function createPaymentHeaderExample(
  message: TransferAuthorizationMessage,
  signature: string
) {
  console.log('📦 Creating X402 Payment Header\n');

  const paymentSignature = {
    signature,
    authorization: message,
    quote_issued_at: Math.floor(Date.now() / 1000),
  };

  const header = createX402PaymentHeader(paymentSignature);

  console.log('X402 Payment Header:');
  console.log(`  Header (base64): ${header.substring(0, 50)}...`);
  console.log(`  Length: ${header.length} characters`);
  console.log();

  // Parse it back to verify
  const parsed = parseX402PaymentHeader(header);
  console.log('Parsed back:');
  console.log(`  Signature: ${parsed?.signature.substring(0, 20)}...`);
  console.log(`  From: ${parsed?.authorization.from}`);
  console.log(`  To: ${parsed?.authorization.to}`);
  console.log(`  Nonce: ${parsed?.authorization.nonce}`);
  console.log();

  return header;
}

/**
 * Example 4: Quote Execution Flow (with mock)
 */
async function quoteExecutionFlowExample() {
  console.log('🔄 Quote Execution Flow\n');

  console.log('Step 1: Create QuoteExecutor');
  const executor = new QuoteExecutor('https://ezpath.myezverse.xyz', {
    agentAddress: '0x1234567890123456789012345678901234567890',
    signingFunction: mockSignMessage,
  });
  console.log('  ✅ Executor ready\n');

  console.log('Step 2: Execute quote (would trigger 402 → sign → retry flow)');
  const request = {
    chain: 'base' as const,
    sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // USDC
    buyToken: '0x4200000000000000000000000000000000000006', // WETH
    sellAmount: '1000000', // 1 USDC
  };

  console.log(`  Selling: ${request.sellAmount} USDC`);
  console.log(`  Buying: WETH`);
  console.log();

  // In production, this would:
  // 1. GET /api/v1/quote → HTTP 402
  // 2. Create authorization message
  // 3. Sign with EIP-3009
  // 4. Retry with X-Payment header
  // 5. Return settlement transaction

  console.log('  Expected flow:');
  console.log('    1️⃣  GET /api/v1/quote → HTTP 402 Payment Required');
  console.log('    2️⃣  Extract fee: $0.03 USDC (30,000 atomic)');
  console.log('    3️⃣  Create TransferWithAuthorization message');
  console.log('    4️⃣  Sign with EIP-712 domain');
  console.log('    5️⃣  Build X-Payment header (base64)');
  console.log('    6️⃣  GET /api/v1/quote with X-Payment header');
  console.log('    7️⃣  HTTP 200 OK with settlement_tx');
  console.log();
}

/**
 * Example 5: Payment Tiers and Sizing
 */
function paymentTierExample() {
  console.log('💰 Payment Tiers\n');

  Object.entries(PAYMENT_TIERS).forEach(([key, tier]) => {
    console.log(`${tier.name} (${key}):`);
    console.log(`  Cost: $${tier.costUSDC} USDC`);
    console.log(`  Atomic: ${tier.costAtomic.toString()} (6 decimals)`);
    console.log(`  Features: ${tier.description}`);
    console.log();
  });

  // Determine tier by amount
  const amounts = [
    BigInt(30000),   // basic
    BigInt(100000),  // resilient
    BigInt(500000),  // institutional
  ];

  console.log('Tier detection:');
  amounts.forEach((amount) => {
    const tier = getTierByAmount(amount);
    console.log(`  ${amount.toString().padEnd(6)} atomic → ${tier}`);
  });
  console.log();
}

/**
 * Example 6: Error Handling
 */
async function errorHandlingExample() {
  console.log('⚠️  Error Handling Scenarios\n');

  // Scenario 1: Invalid from address
  console.log('1️⃣  Invalid from address:');
  const badMessage1 = {
    from: '0xinvalid',
    to: TOLL_ADDRESS,
    value: '30000',
    validAfter: 0,
    validBefore: Math.floor(Date.now() / 1000) + 300,
    nonce: '0x' + '0'.repeat(64),
  };
  const validation1 = validateAuthorizationMessage(badMessage1);
  console.log(`   Result: ${validation1.valid ? 'Valid' : 'Invalid'}`);
  console.log(`   Error: ${validation1.error}`);
  console.log();

  // Scenario 2: Expired message
  console.log('2️⃣  Expired authorization:');
  const badMessage2 = {
    from: '0x1234567890123456789012345678901234567890',
    to: TOLL_ADDRESS,
    value: '30000',
    validAfter: 0,
    validBefore: Math.floor(Date.now() / 1000) - 300, // Expired
    nonce: '0x' + '0'.repeat(64),
  };
  const validation2 = validateAuthorizationMessage(badMessage2);
  console.log(`   Result: ${validation2.valid ? 'Valid' : 'Invalid'}`);
  console.log(`   Error: ${validation2.error}`);
  console.log();

  // Scenario 3: Invalid nonce
  console.log('3️⃣  Invalid nonce:');
  const badMessage3 = {
    from: '0x1234567890123456789012345678901234567890',
    to: TOLL_ADDRESS,
    value: '30000',
    validAfter: 0,
    validBefore: Math.floor(Date.now() / 1000) + 300,
    nonce: '0xbad', // Too short
  };
  const validation3 = validateAuthorizationMessage(badMessage3);
  console.log(`   Result: ${validation3.valid ? 'Valid' : 'Invalid'}`);
  console.log(`   Error: ${validation3.error}`);
  console.log();
}

/**
 * Example 7: Configuration Reference
 */
function configurationReferenceExample() {
  console.log('⚙️  X402 Configuration Reference\n');

  console.log('Protocol Settings:');
  console.log(`  Protocol: ${X402_CONFIG.protocol}`);
  console.log(`  Version: ${X402_CONFIG.version}`);
  console.log(`  Method: ${X402_CONFIG.paymentMethod}`);
  console.log();

  console.log('Base Chain:');
  console.log(`  Chain: ${X402_CONFIG.chain}`);
  console.log(`  Chain ID: ${X402_CONFIG.chainId}`);
  console.log();

  console.log('USDC Configuration:');
  console.log(`  Address: ${X402_CONFIG.usdcAddress}`);
  console.log(`  Toll Address: ${X402_CONFIG.tollAddress}`);
  console.log();

  console.log('Retry Settings:');
  console.log(`  Max Retries: ${X402_CONFIG.maxRetries}`);
  console.log(`  Retry Delay: ${X402_CONFIG.retryDelayMs}ms`);
  console.log();

  console.log('Quote TTL:');
  console.log(`  ${X402_CONFIG.quoteTTL} seconds`);
  console.log();
}

/**
 * Example 8: Integration with Agent
 */
async function agentIntegrationExample() {
  console.log('🤖 Integration with Arena Agent\n');

  console.log('How agents use X402 payments:\n');

  console.log('1. Agent initializes QuoteExecutor:');
  console.log(`
import { QuoteExecutor } from '@infiniteezverse/monskills-ezpath/dist/payments';
import { ethers } from 'ethers';

const signer = new ethers.Wallet(agentPrivateKey);
const executor = new QuoteExecutor('https://ezpath.myezverse.xyz', {
  agentAddress: agent.address,
  signingFunction: (message) => signer.signTypedData(
    USDC_BASE_DOMAIN,
    TRANSFER_WITH_AUTHORIZATION_TYPE,
    message
  ),
});
`);

  console.log('2. Agent gets quotes with payment handling:');
  console.log(`
const result = await executor.executeQuote({
  chain: 'base',
  sellToken: USDC,
  buyToken: WETH,
  sellAmount: '1000000',
});

if (result.success) {
  console.log('Quote: ' + result.data.price);
  console.log('Settlement: ' + result.data.settlement_tx);
  console.log('Paid: $' + result.data.tier);
} else if (result.paymentRequired) {
  console.log('Payment failed, refund: ' + result.estimatedFee.usd + ' USDC');
}
`);

  console.log('3. Settlement transaction is ready:');
  console.log(`
const settlement_tx = result.data.settlement_tx;
if (settlement_tx) {
  // Broadcast to verify on-chain
  const receipt = await provider.getTransactionReceipt(settlement_tx);
  console.log('Confirmed: ' + receipt.status);
}
`);
}

/**
 * Main: Run all examples
 */
async function main() {
  try {
    console.log('🔐 X402 EIP-3009 Payment Examples\n');
    console.log('='.repeat(60) + '\n');

    const authMessage = await createAuthorizationExample();
    console.log('='.repeat(60) + '\n');

    const signature = await signMessageExample(authMessage);
    if (!signature) throw new Error('Signing failed');
    console.log('='.repeat(60) + '\n');

    const header = await createPaymentHeaderExample(authMessage, signature);
    console.log('='.repeat(60) + '\n');

    await quoteExecutionFlowExample();
    console.log('='.repeat(60) + '\n');

    paymentTierExample();
    console.log('='.repeat(60) + '\n');

    await errorHandlingExample();
    console.log('='.repeat(60) + '\n');

    configurationReferenceExample();
    console.log('='.repeat(60) + '\n');

    await agentIntegrationExample();

    console.log('\n' + '='.repeat(60));
    console.log('✅ X402 payment examples completed!');
  } catch (error) {
    console.error('Error:', error);
    process.exit(1);
  }
}

export {
  createAuthorizationExample,
  signMessageExample,
  createPaymentHeaderExample,
  quoteExecutionFlowExample,
  paymentTierExample,
  errorHandlingExample,
  configurationReferenceExample,
  agentIntegrationExample,
};
export default main;

if (require.main === module) {
  main().catch(console.error);
}
