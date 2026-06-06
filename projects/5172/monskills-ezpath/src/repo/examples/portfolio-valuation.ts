/**
 * Portfolio Valuation Agent Example
 * Demonstrates how agents can use EZ-Path for real-time portfolio pricing
 */

import { batchQuotes, getPrice, EZPathQuoteRequest } from '../src/index';

/**
 * Portfolio asset definition
 */
interface PortfolioAsset {
  symbol: string;
  address: string;
  chain: 'base' | 'monad';
  balance: string; // In atomic units
  decimals: number;
}

/**
 * USDC reference token on each chain
 */
const USDC_ADDRESS = {
  base: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
  monad: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // Same address for consistency
};

/**
 * Sample portfolio with multiple assets
 */
const samplePortfolio: PortfolioAsset[] = [
  {
    symbol: 'WETH',
    address: '0x4200000000000000000000000000000000000006',
    chain: 'base',
    balance: '2000000000000000000', // 2 WETH (18 decimals)
    decimals: 18,
  },
  {
    symbol: 'USDC',
    address: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
    chain: 'base',
    balance: '50000000', // 50 USDC (6 decimals)
    decimals: 6,
  },
  {
    symbol: 'USDbC',
    address: '0x50c5725949A6F0c72EC20E08a6DE0146F30F1F75',
    chain: 'base',
    balance: '30000000', // 30 USDbC (6 decimals)
    decimals: 6,
  },
  {
    symbol: 'AERO',
    address: '0x940181a94A35D629567C83f289D0aaB5391F3eAa',
    chain: 'base',
    balance: '100000000000000000000', // 100 AERO (18 decimals)
    decimals: 18,
  },
];

/**
 * Valuation result for a single asset
 */
interface AssetValuation {
  asset: PortfolioAsset;
  priceInUSDC: string;
  valueInUSDC: string;
  humanReadablePrice: string;
  humanReadableValue: string;
  quotingEngine: string;
  timestamp: number;
}

/**
 * Get price for a single asset
 */
async function getAssetPrice(
  asset: PortfolioAsset,
  usdcToken: string
): Promise<AssetValuation | null> {
  try {
    const result = await getPrice(
      asset.chain,
      asset.address, // Sell this asset
      usdcToken, // Buy USDC
      asset.balance // Sell entire balance
    );

    if ('price' in result) {
      // Calculate human-readable values
      const balanceDecimal = parseInt(asset.balance) / Math.pow(10, asset.decimals);
      const valueInUSDC = result.price; // This is the total USDC value

      return {
        asset,
        priceInUSDC: result.price,
        valueInUSDC,
        humanReadablePrice: (parseFloat(result.price) / balanceDecimal).toFixed(6),
        humanReadableValue: (parseFloat(result.price) / Math.pow(10, 6)).toFixed(2), // Normalize to USDC (6 decimals)
        quotingEngine: result.sources[0] || 'Unknown',
        timestamp: Date.now(),
      };
    } else {
      console.warn(`❌ Failed to price ${asset.symbol}: ${result.error}`);
      return null;
    }
  } catch (error) {
    console.error(`Error pricing ${asset.symbol}:`, error);
    return null;
  }
}

/**
 * Valuate entire portfolio
 */
async function valuatePortfolio(portfolio: PortfolioAsset[]): Promise<{
  assets: AssetValuation[];
  totalValueUSDC: string;
  timestamp: number;
  assetCount: number;
  successCount: number;
}> {
  console.log('📊 Starting portfolio valuation...\n');

  // Get prices for all assets
  const valuations: AssetValuation[] = [];

  for (const asset of portfolio) {
    const usdcAddress = USDC_ADDRESS[asset.chain];
    console.log(`⏳ Pricing ${asset.symbol} on ${asset.chain}...`);
    const valuation = await getAssetPrice(asset, usdcAddress);

    if (valuation) {
      valuations.push(valuation);
      console.log(
        `   ✅ ${asset.symbol}: $${valuation.humanReadableValue} (via ${valuation.quotingEngine})`
      );
    }
  }

  // Calculate total
  const totalValueUSDC = valuations
    .reduce((sum, v) => sum + parseFloat(v.valueInUSDC), 0)
    .toString();

  const totalValueUSDC_human = (parseInt(totalValueUSDC) / 1e6).toFixed(2);

  console.log(`\n💰 Total Portfolio Value: $${totalValueUSDC_human} USDC`);

  return {
    assets: valuations,
    totalValueUSDC,
    timestamp: Date.now(),
    assetCount: portfolio.length,
    successCount: valuations.length,
  };
}

/**
 * Generate portfolio report
 */
function generateReport(valuation: Awaited<ReturnType<typeof valuatePortfolio>>) {
  console.log('\n' + '='.repeat(60));
  console.log('📈 PORTFOLIO VALUATION REPORT');
  console.log('='.repeat(60));

  const totalValue = parseInt(valuation.totalValueUSDC) / 1e6;

  console.log(`\nValued at: ${new Date(valuation.timestamp).toISOString()}`);
  console.log(`Total Value: $${totalValue.toFixed(2)} USDC`);
  console.log(`Assets Valued: ${valuation.successCount}/${valuation.assetCount}`);

  console.log('\n' + '-'.repeat(60));
  console.log('ASSET BREAKDOWN');
  console.log('-'.repeat(60));

  valuation.assets.forEach((v) => {
    const percentage = ((parseFloat(v.valueInUSDC) / parseInt(valuation.totalValueUSDC)) * 100).toFixed(1);
    const bar = '█'.repeat(Math.floor(parseFloat(percentage) / 2));

    console.log(`\n${v.asset.symbol}`);
    console.log(`  Balance: ${(parseInt(v.asset.balance) / Math.pow(10, v.asset.decimals)).toFixed(4)}`);
    console.log(`  Price: $${(parseFloat(v.humanReadablePrice)).toFixed(6)} per unit`);
    console.log(`  Value: $${(parseFloat(v.valueInUSDC) / 1e6).toFixed(2)} (${percentage}%)`);
    console.log(`  ${bar} ${percentage}%`);
    console.log(`  Quoted by: ${v.quotingEngine}`);
  });

  console.log('\n' + '='.repeat(60));
}

/**
 * Agent decision logic based on portfolio value
 */
async function makeAgentDecisions(valuation: Awaited<ReturnType<typeof valuatePortfolio>>) {
  const totalValue = parseInt(valuation.totalValueUSDC) / 1e6;

  console.log('\n🤖 AGENT DECISION LOGIC');
  console.log('='.repeat(60));

  // Example: Rebalancing decision
  console.log('\n1️⃣  Rebalancing Check:');
  const ethAsset = valuation.assets.find((v) => v.asset.symbol === 'WETH');
  if (ethAsset) {
    const ethPercent = (parseFloat(ethAsset.valueInUSDC) / parseInt(valuation.totalValueUSDC)) * 100;
    const ethTarget = 50;

    if (ethPercent > ethTarget + 5) {
      console.log(`   ⚠️  WETH is ${ethPercent.toFixed(1)}% of portfolio (target: ${ethTarget}%)`);
      console.log(`   🎯 Recommend: SELL ${(ethPercent - ethTarget).toFixed(1)}% of WETH`);
    } else if (ethPercent < ethTarget - 5) {
      console.log(`   ⚠️  WETH is ${ethPercent.toFixed(1)}% of portfolio (target: ${ethTarget}%)`);
      console.log(`   🎯 Recommend: BUY ${(ethTarget - ethPercent).toFixed(1)}% more WETH`);
    } else {
      console.log(`   ✅ WETH allocation is balanced at ${ethPercent.toFixed(1)}%`);
    }
  }

  // Example: Risk assessment
  console.log('\n2️⃣  Risk Assessment:');
  if (totalValue > 1000) {
    console.log(`   ⚠️  Portfolio value ($${totalValue.toFixed(2)}) exceeds liquidity target`);
    console.log(`   🎯 Recommend: Distribute to multiple wallets for security`);
  } else {
    console.log(`   ✅ Portfolio size is within safe parameters`);
  }

  // Example: Yield opportunity
  console.log('\n3️⃣  Yield Opportunities:');
  const hasUSDC = valuation.assets.find((v) => v.asset.symbol === 'USDC');
  if (hasUSDC && parseFloat(hasUSDC.valueInUSDC) / 1e6 > 10) {
    console.log(`   💡 USDC balance (${(parseFloat(hasUSDC.valueInUSDC) / 1e6).toFixed(2)}) eligible for lending`);
    console.log(`   🎯 Recommend: Deposit to Aave or Compound for yield`);
  }

  console.log('\n' + '='.repeat(60));
}

/**
 * Main: Run portfolio valuation
 */
async function main() {
  try {
    console.log('🚀 Portfolio Valuation Agent v1.0');
    console.log('Using EZ-Path DEX quotes for real-time pricing\n');

    // Valuate portfolio
    const valuation = await valuatePortfolio(samplePortfolio);

    // Generate report
    generateReport(valuation);

    // Make agent decisions
    await makeAgentDecisions(valuation);

    console.log('\n✅ Portfolio valuation complete!');
  } catch (error) {
    console.error('Fatal error:', error);
    process.exit(1);
  }
}

export { valuatePortfolio, generateReport, makeAgentDecisions };
export default main;

if (require.main === module) {
  main().catch(console.error);
}
