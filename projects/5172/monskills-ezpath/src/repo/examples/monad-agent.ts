/**
 * Monad Native Agent Example
 * Demonstrates agent workflows optimized for Monad's high-throughput environment
 *
 * Key differences from other chains:
 * - Sub-2s block time enables real-time pricing
 * - High TPS supports aggressive polling and batch operations
 * - Native MON token (not wrapped) for optimal gas
 * - Aerodrome as primary DEX (100% liquidity on Monad)
 */

import { getPrice, getQuote, batchQuotes, EZPathQuoteRequest } from '../src/index';
import { MONAD_CONFIG, getMonadRPC, recommendMonadVenue } from '../src/config/monad';

/**
 * Monad Agent Identity
 */
interface MonadAgent {
  id: string;
  address: string;
  chain: 'monad';
  strategy: 'arbitrage' | 'market-making' | 'yield-farming' | 'speculation';
  portfolio: {
    MON: bigint;
    USDC: bigint;
    WETH: bigint;
    [token: string]: bigint;
  };
}

/**
 * Example 1: Real-time Price Monitoring on Monad
 * Leverage Monad's high throughput for continuous price tracking
 */
async function monitorPricesRealtimeExample() {
  console.log('📊 Monad Real-time Price Monitor\n');

  const pairs = [
    {
      name: 'MON/USDC',
      sellToken: MONAD_CONFIG.tokens.MON,
      buyToken: MONAD_CONFIG.tokens.USDC,
    },
    {
      name: 'WETH/MON',
      sellToken: MONAD_CONFIG.tokens.WETH,
      buyToken: MONAD_CONFIG.tokens.MON,
    },
    {
      name: 'USDC/USDT',
      sellToken: MONAD_CONFIG.tokens.USDC,
      buyToken: MONAD_CONFIG.tokens.USDT,
    },
  ];

  const amount = '1000000'; // 1 unit in atomic form

  console.log('🔄 Querying Monad venues...\n');

  // Batch quote all pairs simultaneously
  // Monad's high TPS means this completes in <1 second
  const quotes = await batchQuotes(
    pairs.map((pair) => ({
      chain: 'monad',
      sellToken: pair.sellToken,
      buyToken: pair.buyToken,
      sellAmount: amount,
    }))
  );

  // Display results
  quotes.forEach((quote, index) => {
    const pair = pairs[index];
    if (quote.success && quote.data) {
      console.log(`✅ ${pair.name}: ${quote.data.price}`);
      console.log(`   Best venue: ${quote.data.routingEngine}`);
      console.log(`   All venues: ${quote.data.sources.map((s) => s.name).join(', ')}\n`);
    } else {
      console.log(`❌ ${pair.name}: ${quote.error}\n`);
    }
  });
}

/**
 * Example 2: Monad Arbitrage Detection
 * Monitor Monad pairs and cross-chain opportunities
 */
async function monitorArbitrageExample() {
  console.log('🔍 Monad Arbitrage Opportunity Detector\n');

  // Check MON/USDC spread across different venues
  const quoteRequest: EZPathQuoteRequest = {
    chain: 'monad',
    sellToken: MONAD_CONFIG.tokens.MON,
    buyToken: MONAD_CONFIG.tokens.USDC,
    sellAmount: '1000000000000000000', // 1 MON (18 decimals)
  };

  const quote = await getQuote(quoteRequest);

  if (quote.success && quote.data) {
    console.log(`📈 MON/USDC Quote Analysis`);
    console.log(`Request ID: ${quote.data.request_id}\n`);

    // Find best and worst venues
    const sorted = [...quote.data.sources].sort((a, b) =>
      BigInt(b.buyAmount) - BigInt(a.buyAmount)
    );

    const best = sorted[0];
    const worst = sorted[sorted.length - 1];

    const spread =
      ((BigInt(best.buyAmount) - BigInt(worst.buyAmount)) /
        BigInt(worst.buyAmount)) *
      100n;

    console.log(`🏆 Best: ${best.name} (${best.buyAmount} USDC)`);
    console.log(`📉 Worst: ${worst.name} (${worst.buyAmount} USDC)`);
    console.log(`\n📊 Spread: ${spread.toString()}%`);

    if (spread > 100n) {
      console.log(
        `\n⚠️  Significant spread detected! Arbitrage opportunity exists.`
      );
      console.log(
        `Strategy: Buy on ${worst.name}, sell on ${best.name}\n`
      );
    } else {
      console.log(`\n✅ Market is efficient. No arbitrage opportunity.\n`);
    }

    // Detailed venue breakdown
    console.log('📋 All Venues:');
    sorted.forEach((venue, index) => {
      const rank = index + 1;
      const icon = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : '  ';
      console.log(`   ${icon} #${rank} ${venue.name}: ${venue.buyAmount} USDC`);
    });
  } else {
    console.log(`❌ Quote failed: ${quote.error}`);
  }
}

/**
 * Example 3: Monad Agent Auto-Rebalancing
 * Leverage high throughput for continuous portfolio optimization
 */
async function autoRebalanceExample() {
  console.log('\n⚖️  Monad Agent Auto-Rebalancing\n');

  // Simulated agent
  const agent: MonadAgent = {
    id: 'monad-agent-001',
    address: '0x1234567890123456789012345678901234567890',
    chain: 'monad',
    strategy: 'market-making',
    portfolio: {
      MON: BigInt('10000000000000000000'), // 10 MON
      USDC: BigInt('50000000'), // 50 USDC (6 decimals)
      WETH: BigInt('2000000000000000000'), // 2 WETH (18 decimals)
    },
  };

  console.log(`Agent: ${agent.id}`);
  console.log(`Strategy: ${agent.strategy}`);
  console.log(`Current holdings: ${JSON.stringify(agent.portfolio)}\n`);

  // Define rebalance targets
  const targets = {
    MON: 0.4,    // 40%
    USDC: 0.35,  // 35%
    WETH: 0.25,  // 25%
  };

  console.log('📊 Rebalance Targets:');
  Object.entries(targets).forEach(([token, pct]) => {
    console.log(`   ${token}: ${(pct * 100).toFixed(0)}%`);
  });
  console.log();

  // Get current prices
  const prices = await batchQuotes([
    {
      chain: 'monad',
      sellToken: MONAD_CONFIG.tokens.MON,
      buyToken: MONAD_CONFIG.tokens.USDC,
      sellAmount: '1000000000000000000',
    },
    {
      chain: 'monad',
      sellToken: MONAD_CONFIG.tokens.WETH,
      buyToken: MONAD_CONFIG.tokens.USDC,
      sellAmount: '1000000000000000000',
    },
  ]);

  if (prices.every((p) => p.success)) {
    // Calculate current allocation
    const monPrice = parseFloat(prices[0].data!.price);
    const ethPrice = parseFloat(prices[1].data!.price);

    const portfolio = {
      MON: (Number(agent.portfolio.MON) / 1e18) * monPrice,
      USDC: Number(agent.portfolio.USDC) / 1e6,
      WETH: (Number(agent.portfolio.WETH) / 1e18) * ethPrice,
    };

    const totalValue = portfolio.MON + portfolio.USDC + portfolio.WETH;
    const current = {
      MON: portfolio.MON / totalValue,
      USDC: portfolio.USDC / totalValue,
      WETH: portfolio.WETH / totalValue,
    };

    console.log('💰 Current Allocation (in USDC):');
    Object.entries(portfolio).forEach(([token, value]) => {
      const pct = (current[token as keyof typeof current] * 100).toFixed(1);
      console.log(`   ${token}: $${value.toFixed(2)} (${pct}%)`);
    });
    console.log();

    // Identify rebalancing needs
    console.log('🎯 Rebalancing Actions:');
    let needsRebalance = false;

    Object.entries(targets).forEach(([token, targetPct]) => {
      const currentPct = current[token as keyof typeof current];
      const diff = (currentPct - targetPct) * 100;

      if (Math.abs(diff) > 2) {
        needsRebalance = true;
        if (diff > 0) {
          console.log(`   ↘️  REDUCE ${token} by ${Math.abs(diff).toFixed(1)}%`);
        } else {
          console.log(`   ↗️  INCREASE ${token} by ${Math.abs(diff).toFixed(1)}%`);
        }
      } else {
        console.log(`   ✅ ${token} is balanced`);
      }
    });

    if (!needsRebalance) {
      console.log('\n✅ Portfolio is already well-balanced!');
    }
  }
}

/**
 * Example 4: Monad Venue Recommendation
 * Get optimal venue for specific token pairs
 */
async function venueRecommendationExample() {
  console.log('\n🏦 Monad Venue Recommendation\n');

  const pairs = [
    { token: 'MON', name: 'MON/USDC' },
    { token: MONAD_CONFIG.tokens.USDC, name: 'USDC/USDT' },
    { token: MONAD_CONFIG.tokens.WETH, name: 'WETH/MON' },
  ];

  console.log('📍 Recommended Venues by Pair:\n');

  pairs.forEach((pair) => {
    const recommended = recommendMonadVenue(
      pair.token,
      MONAD_CONFIG.tokens.USDC
    );
    const venueConfig = Object.entries(MONAD_CONFIG.venues).find(
      ([key]) => key === recommended
    );

    console.log(`${pair.name}:`);
    console.log(`   Recommended: ${venueConfig?.[1].name || 'Unknown'}`);
    console.log(`   Features: ${venueConfig?.[1].features?.join(', ') || 'N/A'}`);
    console.log(`   Priority: ${venueConfig?.[1].priority}\n`);
  });
}

/**
 * Example 5: Monad High-Frequency Monitoring
 * Continuous price tracking (leveraging Monad's high TPS)
 */
async function highFrequencyMonitorExample() {
  console.log('\n⚡ High-Frequency Price Monitor (Mock)\n');
  console.log(
    'In production, this would update every 2 seconds on Monad\n'
  );

  const pair = {
    sellToken: MONAD_CONFIG.tokens.MON,
    buyToken: MONAD_CONFIG.tokens.USDC,
    sellAmount: '1000000000000000000',
  };

  let previousPrice: string | null = null;

  for (let i = 0; i < 3; i++) {
    const quote = await getPrice(
      'monad',
      pair.sellToken,
      pair.buyToken,
      pair.sellAmount
    );

    if ('price' in quote) {
      const currentPrice = quote.price;
      const change = previousPrice
        ? (
          (parseFloat(currentPrice) - parseFloat(previousPrice)) /
          parseFloat(previousPrice)
        ) * 100
        : 0;

      const arrow = change > 0 ? '📈' : change < 0 ? '📉' : '➡️';

      console.log(
        `${arrow} [${new Date().toISOString()}] MON/USDC: ${currentPrice} (${change > 0 ? '+' : ''}${change.toFixed(3)}%)`
      );
      previousPrice = currentPrice;
    } else {
      console.log(`❌ Quote failed: ${quote.error}`);
    }

    // In real implementation, wait 2 seconds (Monad's ~block time)
    if (i < 2) {
      console.log('   ⏳ Waiting...');
      // await sleep(2000);
    }
  }
}

/**
 * Main: Run all Monad-native examples
 */
async function main() {
  try {
    console.log(
      '🌟 Monad Native Agent Examples\n'
    );
    console.log('Chain: Monad (ChainID: 10143)');
    console.log(`RPC: ${MONAD_CONFIG.rpc.primary}\n`);
    console.log('='.repeat(60) + '\n');

    await monitorPricesRealtimeExample();
    console.log('='.repeat(60));

    await monitorArbitrageExample();
    console.log('='.repeat(60));

    await autoRebalanceExample();
    console.log('='.repeat(60));

    await venueRecommendationExample();
    console.log('='.repeat(60));

    await highFrequencyMonitorExample();

    console.log('\n' + '='.repeat(60));
    console.log('✅ All Monad agent examples completed!');
  } catch (error) {
    console.error('Fatal error:', error);
    process.exit(1);
  }
}

export {
  monitorPricesRealtimeExample,
  monitorArbitrageExample,
  autoRebalanceExample,
  venueRecommendationExample,
  highFrequencyMonitorExample,
};
export default main;

if (require.main === module) {
  main().catch(console.error);
}
