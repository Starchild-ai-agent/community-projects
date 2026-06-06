/**
 * Basic MONSKILLS Agent Usage Examples
 * Demonstrates how agents can use EZ-Path for DEX pricing
 */

import { getPrice, getQuote, batchQuotes, EZPathQuoteRequest } from '../src/index';

/**
 * Example 1: Quick price lookup
 * Simplest way to get a DEX price quote
 */
async function quickPriceExample() {
  console.log('=== Quick Price Lookup ===');

  const result = await getPrice(
    'base',
    '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // USDC on Base
    '0x4200000000000000000000000000000000000006', // WETH on Base
    '1000000' // 1 USDC (6 decimals)
  );

  if ('price' in result) {
    console.log(`✅ Got price: ${result.price}`);
    console.log(`   From venues: ${result.sources.join(', ')}`);
  } else {
    console.log(`❌ Error: ${result.error}`);
  }
}

/**
 * Example 2: Full quote with venue details
 * Returns all 10 venue quotes and settlement info
 */
async function fullQuoteExample() {
  console.log('\n=== Full Quote with Venue Details ===');

  const request: EZPathQuoteRequest = {
    chain: 'base',
    sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // USDC
    buyToken: '0x4200000000000000000000000000000000000006', // WETH
    sellAmount: '10000000', // 10 USDC
    slippagePercentage: 0.5, // 0.5% slippage
  };

  const result = await getQuote(request);

  if (result.success && result.data) {
    console.log(`✅ Quote successful (ID: ${result.data.request_id})`);
    console.log(`   Sell: ${result.data.sellAmount} ${result.data.sellToken}`);
    console.log(`   Buy: ${result.data.buyAmount} ${result.data.buyToken}`);
    console.log(`   Price: ${result.data.price} WETH per USDC`);
    console.log(`   Best routing engine: ${result.data.routingEngine}`);
    console.log(`   Tier: ${result.data.tier}`);
    console.log(`   All venues quoted: ${result.data.sources.map(s => s.name).join(', ')}`);

    // If settlement_tx is present, it means EZ-Path already executed
    if (result.data.settlement_tx) {
      console.log(`   ✅ Settlement TX: ${result.data.settlement_tx}`);
    }
  } else if (result.paymentRequired) {
    console.log(`⚠️  Payment required: ${result.error}`);
    console.log(`   Fee: ${result.estimatedFee?.usd} USDC (${result.estimatedFee?.atomic} atomic)`);
    console.log(`   Token: ${result.estimatedFee?.token}`);
  } else {
    console.log(`❌ Error: ${result.error}`);
  }
}

/**
 * Example 3: Batch quotes for portfolio valuation
 * Quote multiple token pairs in parallel
 */
async function batchQuoteExample() {
  console.log('\n=== Batch Quotes (Portfolio Valuation) ===');

  const pairs: EZPathQuoteRequest[] = [
    {
      chain: 'base',
      sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // USDC
      buyToken: '0x4200000000000000000000000000000000000006', // WETH
      sellAmount: '1000000', // 1 USDC
    },
    {
      chain: 'base',
      sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // USDC
      buyToken: '0x50c5725949A6F0c72EC20E08a6DE0146F30F1F75', // USDbC
      sellAmount: '1000000', // 1 USDC
    },
    {
      chain: 'monad',
      sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // USDC (on Monad)
      buyToken: '0x4200000000000000000000000000000000000006', // WETH (on Monad)
      sellAmount: '5000000', // 5 USDC
    },
  ];

  const results = await batchQuotes(pairs);

  results.forEach((result, index) => {
    const pair = pairs[index];
    if (result.success && result.data) {
      console.log(`✅ Pair ${index + 1} (${pair.chain}): ${result.data.price}`);
    } else {
      console.log(`❌ Pair ${index + 1} failed: ${result.error}`);
    }
  });

  // Calculate total portfolio value
  const totalValue = results.reduce((sum, result) => {
    if (result.success && result.data) {
      return sum + parseFloat(result.data.buyAmount);
    }
    return sum;
  }, 0);

  console.log(`   Total portfolio value: ${totalValue.toFixed(6)} (combined units)`);
}

/**
 * Example 4: Error handling
 * Shows how to gracefully handle various error cases
 */
async function errorHandlingExample() {
  console.log('\n=== Error Handling ===');

  // Missing parameters
  const invalidRequest: any = {
    chain: 'base',
    sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
    // buyToken is missing!
    sellAmount: '1000000',
  };

  const result = await getQuote(invalidRequest);
  if (!result.success) {
    console.log(`✅ Caught validation error: ${result.error}`);
  }

  // Invalid chain
  const invalidChain = await getPrice(
    'unknownchain' as any,
    '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
    '0x4200000000000000000000000000000000000006',
    '1000000'
  );

  if ('error' in invalidChain) {
    console.log(`✅ Caught chain error: ${invalidChain.error.substring(0, 60)}...`);
  }
}

/**
 * Example 5: Agent integration pattern
 * How an agent would use EZ-Path within decision logic
 */
async function agentIntegrationPattern() {
  console.log('\n=== Agent Integration Pattern ===');

  // Simulate agent intent
  const agentIntent = {
    action: 'swap',
    tokenIn: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // USDC
    tokenOut: '0x4200000000000000000000000000000000000006', // WETH
    amountIn: '10000000', // 10 USDC
    chain: 'base',
    minExpectedOutput: '0.004', // Agent's minimum acceptable output
  };

  console.log(`🤖 Agent Intent: Swap ${agentIntent.amountIn} ${agentIntent.tokenIn}`);
  console.log(`   → to ${agentIntent.tokenOut}`);
  console.log(`   → Minimum output required: ${agentIntent.minExpectedOutput}`);

  // Get quote from EZ-Path
  const quote = await getQuote({
    chain: agentIntent.chain as any,
    sellToken: agentIntent.tokenIn,
    buyToken: agentIntent.tokenOut,
    sellAmount: agentIntent.amountIn,
  });

  if (quote.success && quote.data) {
    const expectedOutput = quote.data.buyAmount;
    const meetsMinimum = parseFloat(expectedOutput) >= parseFloat(agentIntent.minExpectedOutput);

    console.log(`\n📊 Quote Result:`);
    console.log(`   Expected output: ${expectedOutput}`);
    console.log(`   Best engine: ${quote.data.routingEngine}`);
    console.log(`   Meets minimum? ${meetsMinimum ? '✅ Yes' : '❌ No'}`);

    if (meetsMinimum) {
      console.log(`\n🚀 Agent would APPROVE this swap`);
    } else {
      console.log(`\n⛔ Agent would REJECT this swap (output too low)`);
    }
  } else {
    console.log(`\n⛔ Agent would REJECT (quote failed: ${quote.error})`);
  }
}

/**
 * Run all examples
 */
async function runExamples() {
  try {
    await quickPriceExample();
    await fullQuoteExample();
    await batchQuoteExample();
    await errorHandlingExample();
    await agentIntegrationPattern();
  } catch (error) {
    console.error('Example error:', error);
  }
}

// Export for MONSKILLS integration
export default runExamples;
export { quickPriceExample, fullQuoteExample, batchQuoteExample, errorHandlingExample, agentIntegrationPattern };

// Run if executed directly
if (require.main === module) {
  runExamples().catch(console.error);
}
