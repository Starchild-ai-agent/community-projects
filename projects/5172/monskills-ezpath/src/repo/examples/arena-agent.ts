/**
 * Arena Competition Agent Example
 * Demonstrates how Arena agents use EZ-Path for bankroll management in poker-style competitions
 */

import { getPrice, getQuote, EZPathQuoteRequest } from '../src/index';

/**
 * Agent bankroll state
 */
interface AgentBankroll {
  agentId: string;
  initialBankroll: bigint;
  currentBankroll: bigint;
  tokenAddress: string;
  chain: 'base' | 'monad';
  buyInAmount: bigint;
  historicalValues: { timestamp: number; valueInUSDC: string }[];
}

/**
 * Arena competition game state
 */
interface ArenaGameState {
  gameId: string;
  agentId: string;
  tableSize: number;
  chipStack: bigint; // Agent's current chip stack
  blindLevel: number;
  roundNumber: number;
  timeRemaining: number; // Seconds
}

/**
 * Decision making context
 */
interface GameDecisionContext {
  bankrollValueUSDC: string;
  chipStackInUSDC: string;
  buyInCostUSDC: string;
  riskOfRuin: number; // 0-1 probability
  optimalStackSize: string;
  recommendation: 'aggressive' | 'balanced' | 'conservative' | 'exit';
  confidenceLevel: number; // 0-1
}

/**
 * Calculate risk of ruin given bankroll and buyins
 * Based on Kelly Criterion and Gambler's Ruin theory
 */
function calculateRiskOfRuin(
  bankrollInBuyins: number,
  winRate: number = 0.52, // 52% win rate assumption
): number {
  // For 52% win rate, approximate RoR using simplified Kelly formula
  const edgePercentage = 2 * (winRate - 0.5);
  const variance = 2 * winRate * (1 - winRate);

  // Risk of ruin approximation (lower bankroll = higher risk)
  if (bankrollInBuyins < 1) return 0.95; // Likely to bust out
  if (bankrollInBuyins < 5) return 0.7;
  if (bankrollInBuyins < 10) return 0.4;
  if (bankrollInBuyins < 20) return 0.15;
  if (bankrollInBuyins < 30) return 0.05;
  return 0.01; // Very safe
}

/**
 * Get current bankroll valuation in USDC
 */
async function valuateBankroll(bankroll: AgentBankroll): Promise<string> {
  console.log(`💰 Valuing ${bankroll.agentId}'s bankroll...`);

  try {
    const result = await getPrice(
      bankroll.chain,
      bankroll.tokenAddress,
      '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // USDC
      bankroll.currentBankroll.toString()
    );

    if ('price' in result) {
      console.log(`   ✅ Bankroll: ${result.price} USDC`);
      return result.price;
    } else {
      console.error(`   ❌ Error: ${result.error}`);
      return '0';
    }
  } catch (error) {
    console.error(`   ❌ Valuation failed:`, error);
    return '0';
  }
}

/**
 * Make game decision based on bankroll and chip stack
 */
async function makeGameDecision(
  bankroll: AgentBankroll,
  gameState: ArenaGameState
): Promise<GameDecisionContext> {
  console.log(`\n🎮 Analyzing game decision for ${gameState.agentId}...`);

  // Get current bankroll value
  const bankrollValueUSDC = await valuateBankroll(bankroll);

  // Calculate buyin cost in USDC
  const buyInRequest: EZPathQuoteRequest = {
    chain: bankroll.chain,
    sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // USDC (will show as price to buy 1 unit)
    buyToken: bankroll.tokenAddress,
    sellAmount: bankroll.buyInAmount.toString(),
  };

  let buyInCostUSDC = '0';
  try {
    const buyInQuote = await getQuote(buyInRequest);
    if (buyInQuote.success && buyInQuote.data) {
      buyInCostUSDC = buyInQuote.data.sellAmount;
    }
  } catch (error) {
    console.warn('Could not determine buyin cost');
  }

  // Convert chip stack to USDC equivalent
  // Assume chip stack value scales linearly with agent's bankroll
  const bankrollValue = parseInt(bankrollValueUSDC) / 1e6;
  const chipStackPercentage = Number(gameState.chipStack) / Number(bankroll.currentBankroll);
  const chipStackInUSDC = (bankrollValue * chipStackPercentage).toFixed(2);

  // Calculate bankroll in buyins
  const buyinCost = parseInt(buyInCostUSDC) / 1e6;
  const bankrollInBuyins = bankrollValue / buyinCost;

  // Calculate risk of ruin
  const riskOfRuin = calculateRiskOfRuin(bankrollInBuyins);

  // Determine optimal stack size (typically 20-30 buyins)
  const optimalStackSize = (buyinCost * 25).toFixed(2);

  // Make recommendation
  let recommendation: GameDecisionContext['recommendation'] = 'balanced';
  if (riskOfRuin > 0.5) {
    recommendation = 'conservative';
  } else if (riskOfRuin < 0.05 && bankrollInBuyins > 30) {
    recommendation = 'aggressive';
  } else if (riskOfRuin > 0.7 || bankrollInBuyins < 3) {
    recommendation = 'exit'; // Time to cash out
  }

  const confidence = 1 - riskOfRuin;

  return {
    bankrollValueUSDC,
    chipStackInUSDC,
    buyInCostUSDC: buyinCost.toFixed(2),
    riskOfRuin,
    optimalStackSize,
    recommendation,
    confidenceLevel: confidence,
  };
}

/**
 * Generate strategy recommendation
 */
function generateStrategyRecommendation(context: GameDecisionContext, gameState: ArenaGameState): string {
  const confidencePercent = (context.confidenceLevel * 100).toFixed(0);
  const riskPercent = (context.riskOfRuin * 100).toFixed(0);

  let strategyText = '';

  switch (context.recommendation) {
    case 'aggressive':
      strategyText = `
🚀 AGGRESSIVE STRATEGY (${confidencePercent}% confidence)
   • Bankroll is healthy (${context.bankrollValueUSDC} USDC)
   • Risk of ruin is LOW (${riskPercent}%)
   • Recommended: Play premium hands, take calculated risks
   • Chip stack is strong (${context.chipStackInUSDC} USDC)
   • Consider raising more hands and applying pressure
      `;
      break;

    case 'balanced':
      strategyText = `
⚖️  BALANCED STRATEGY (${confidencePercent}% confidence)
   • Bankroll is solid (${context.bankrollValueUSDC} USDC)
   • Risk of ruin is moderate (${riskPercent}%)
   • Recommended: Play fundamentally sound poker
   • Focus on position and hand selection
   • Avoid unnecessary risks but exploit opportunities
      `;
      break;

    case 'conservative':
      strategyText = `
🛡️  CONSERVATIVE STRATEGY (${confidencePercent}% confidence)
   • Bankroll is limited (${context.bankrollValueUSDC} USDC)
   • Risk of ruin is elevated (${riskPercent}%)
   • Recommended: Play tight, only premium hands
   • Avoid conflicts with strong opponents
   • Wait for favorable spots to accumulate chips
      `;
      break;

    case 'exit':
      strategyText = `
⛔ EXIT RECOMMENDED (${confidencePercent}% confidence)
   • Critical bankroll situation (${context.bankrollValueUSDC} USDC)
   • Risk of ruin is VERY HIGH (${riskPercent}%)
   • SUGGESTION: Exit tournament or reload bankroll
   • Current chips worth: ${context.chipStackInUSDC} USDC
   • Consider cashing out with remaining value
      `;
      break;
  }

  return strategyText;
}

/**
 * Simulate tournament progression
 */
async function simulateTournament() {
  console.log('🏆 Arena Poker Tournament Simulation');
  console.log('='.repeat(60));

  // Initialize agent bankroll
  const agent: AgentBankroll = {
    agentId: 'agent-poker-001',
    initialBankroll: BigInt(10) * BigInt(10 ** 18), // 10 WETH
    currentBankroll: BigInt(10) * BigInt(10 ** 18),
    tokenAddress: '0x4200000000000000000000000000000000000006', // WETH on Base
    chain: 'base',
    buyInAmount: BigInt(1) * BigInt(10 ** 18), // 1 WETH buyin
    historicalValues: [],
  };

  // Simulate different tournament stages
  const stages: ArenaGameState[] = [
    {
      gameId: 'game-001',
      agentId: 'agent-poker-001',
      tableSize: 6,
      chipStack: BigInt(2500), // Starting chips
      blindLevel: 1,
      roundNumber: 1,
      timeRemaining: 3600,
    },
    {
      gameId: 'game-001',
      agentId: 'agent-poker-001',
      tableSize: 6,
      chipStack: BigInt(5200), // Doubled chips
      blindLevel: 2,
      roundNumber: 15,
      timeRemaining: 1800,
    },
    {
      gameId: 'game-001',
      agentId: 'agent-poker-001',
      tableSize: 3, // Down to 3 players
      chipStack: BigInt(12500), // Strong position
      blindLevel: 4,
      roundNumber: 45,
      timeRemaining: 600,
    },
  ];

  for (const gameState of stages) {
    console.log(`\n📍 Stage: Level ${gameState.blindLevel}, Round ${gameState.roundNumber}`);
    console.log(`   Players remaining: ${gameState.tableSize}`);

    // Make decision
    const decision = await makeGameDecision(agent, gameState);

    // Generate recommendation
    const strategy = generateStrategyRecommendation(decision, gameState);
    console.log(strategy);

    // Record history
    agent.historicalValues.push({
      timestamp: Date.now(),
      valueInUSDC: decision.bankrollValueUSDC,
    });

    // Simulate some time passing
    console.log('   ⏳ Simulating tournament progression...\n');
  }

  // Final summary
  console.log('\n' + '='.repeat(60));
  console.log('📊 Tournament Summary');
  console.log('='.repeat(60));

  const finalValue = agent.historicalValues[agent.historicalValues.length - 1]?.valueInUSDC || '0';
  const initialValue = agent.historicalValues[0]?.valueInUSDC || '0';

  console.log(`Initial bankroll: $${(parseInt(initialValue) / 1e6).toFixed(2)} USDC`);
  console.log(`Final bankroll: $${(parseInt(finalValue) / 1e6).toFixed(2)} USDC`);
  console.log(`Result: ${
    parseInt(finalValue) >= parseInt(initialValue)
      ? '✅ PROFIT'
      : '❌ LOSS'
  } of $${Math.abs(parseInt(finalValue) - parseInt(initialValue)) / 1e6} USDC`);

  console.log('\n🎯 Key Insights:');
  console.log('   • EZ-Path enabled real-time bankroll valuation');
  console.log('   • Risk management decisions based on USDC value');
  console.log('   • Dynamic strategy adjusted as bankroll changed');
  console.log('   • All pricing from 10-venue DEX meta-router');
}

export { valuateBankroll, makeGameDecision, generateStrategyRecommendation, simulateTournament };
export default simulateTournament;

if (require.main === module) {
  simulateTournament().catch(console.error);
}
