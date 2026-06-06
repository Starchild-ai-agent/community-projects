/**
 * Arena Agent Template Example
 * Complete template for building competing agents on Arena
 *
 * This example shows:
 * 1. Creating an arena agent
 * 2. Joining a tournament
 * 3. Real-time bankroll management
 * 4. Dynamic strategy selection
 * 5. Tournament progression
 * 6. Exit scenarios
 */

import { Agent, BankrollManager, StrategyEngine } from '../src/agents';
import type { Tournament, AgentConfig } from '../src/agents/types';

/**
 * Example 1: Create an Arena Agent
 */
async function createAgentExample() {
  console.log('🤖 Creating Arena Agent\n');

  const agentConfig: AgentConfig = {
    id: 'arena-agent-001',
    name: 'AlphaPoker-1',
    address: '0x1234567890123456789012345678901234567890',
    chain: 'monad', // Use Monad for high throughput
    bankrollToken: '0x4200000000000000000000000000000000000006', // WETH
    initialBankroll: BigInt('10000000000000000000'), // 10 WETH
    minimumBankroll: BigInt('500000000000000000'), // 0.5 WETH
    skillLevel: 'advanced',
    strategy: 'balanced',
    aggressivenessLevel: 0.6,
    riskTolerance: 0.5,
    targetROI: 0.2, // 20% monthly
  };

  const agent = new Agent(agentConfig);

  console.log(`✅ Agent created: ${agent.name}`);
  console.log(`   Address: ${agent.address}`);
  console.log(`   Bankroll: ${agent.initialBankroll.toString()} ${agent.chain === 'monad' ? 'MON' : 'ETH'}`);
  console.log(`   Strategy: ${agent.strategy}`);
  console.log(`   Skill level: ${agent.skillLevel}\n`);

  return agent;
}

/**
 * Example 2: Check Agent Status
 */
async function checkStatusExample(agent: Agent) {
  console.log('📊 Agent Status Report\n');

  const status = await agent.getStatus();

  console.log(`Agent: ${status.agent.name}`);
  console.log(`Skill: ${status.agent.skillLevel}`);
  console.log();

  console.log('💰 Bankroll:');
  console.log(`   Current: ${status.bankroll.current}`);
  console.log(`   In USDC: $${status.bankroll.inUSDC}`);
  console.log(`   Buyins remaining: ${status.bankroll.buyinsRemaining}`);
  console.log(`   Status: ${status.bankroll.status}`);
  console.log();

  console.log('⚠️  Risk:');
  console.log(`   Risk of ruin: ${status.risk.riskOfRuin}`);
  console.log(`   Health score: ${status.risk.healthScore}/100`);
  console.log(`   Trend: ${status.risk.trend}`);
  console.log();

  console.log('🎯 Strategy:');
  console.log(`   Current: ${status.strategy.current}`);
  console.log(`   Recommended: ${status.strategy.recommended}`);
  console.log(`   Confidence: ${status.strategy.confidence}`);
  console.log(`   Reasoning: ${status.strategy.reasoning}`);
  console.log();

  console.log(`Action: ${status.actions}\n`);

  return status;
}

/**
 * Example 3: Join a Tournament
 */
async function joinTournamentExample(agent: Agent) {
  console.log('🏆 Joining Arena Tournament\n');

  // Create a mock tournament
  const tournament: Tournament = {
    id: 'arena-tournament-001',
    name: 'Friday Night Poker',
    chain: 'monad',
    startTime: Date.now(),
    initialBlind: BigInt('25'),
    smallBlind: BigInt('25'),
    bigBlind: BigInt('50'),
    blindLevel: 1,
    blindIncreaseInterval: 600000, // 10 minutes
    totalPlayers: 45,
    playersRemaining: 45,
    playerPositions: new Map(),
    entryFee: BigInt('1000000000000000000'), // 1 WETH
    prizePool: BigInt('45000000000000000000'), // 45 WETH total
    phase: 'playing',
    roundNumber: 0,
    tableName: 'Table 5',
  };

  console.log(`Tournament: ${tournament.name}`);
  console.log(`Entry fee: ${tournament.entryFee.toString()}`);
  console.log(`Players: ${tournament.totalPlayers}`);
  console.log(`Prize pool: ${tournament.prizePool.toString()}\n`);

  const joined = await agent.joinTournament(tournament, tournament.entryFee);

  if (joined) {
    console.log('✅ Successfully joined tournament!\n');
  } else {
    console.log('❌ Could not join tournament\n');
  }

  return tournament;
}

/**
 * Example 4: Strategy Recommendation
 */
async function strategyRecommendationExample(agent: Agent) {
  console.log('🎯 Strategy Recommendation\n');

  const recommendation = await agent.getStrategyRecommendation();

  console.log(`Current strategy: ${recommendation.currentStrategy}`);
  console.log(`Recommended: ${recommendation.recommendedStrategy}`);
  console.log(`Confidence: ${(recommendation.confidence * 100).toFixed(0)}%`);
  console.log();

  console.log('📈 Metrics:');
  console.log(`   Bankroll health: ${(recommendation.bankrollHealth * 100).toFixed(0)}%`);
  console.log(`   Risk of ruin: ${(recommendation.riskOfRuin * 100).toFixed(1)}%`);
  console.log(`   Table condition: ${recommendation.tableCondition}`);
  console.log(`   Opponent skill: ${recommendation.opponentSkill}`);
  console.log();

  console.log('💡 Suggestions:');
  recommendation.suggestions.forEach((s) => console.log(`   • ${s}`));
  console.log();

  if (recommendation.warningFlags.length > 0) {
    console.log('⚠️  Warnings:');
    recommendation.warningFlags.forEach((w) => console.log(`   ${w}`));
    console.log();
  }

  console.log(`Reasoning: ${recommendation.reasoning}\n`);

  // Update strategy if needed
  const updated = await agent.updateStrategyIfNeeded();
  if (updated) {
    console.log(`✅ Strategy updated to ${agent.strategy}\n`);
  }

  return recommendation;
}

/**
 * Example 5: Simulate Tournament Hands
 */
async function playTournamentExample(agent: Agent) {
  console.log('🎰 Playing Tournament Hands\n');

  // Simulate some hands
  const hands = [
    { type: 'AA', size: 20 },    // Pocket aces, 20 BB stack
    { type: 'KK', size: 18 },    // Kings
    { type: 'AK', size: 16 },    // AK suited
    { type: 'QQ', size: 14 },    // Queens
    { type: 'JT', size: 12 },    // Jack-ten
  ];

  for (const hand of hands) {
    await agent.playHand(hand.type, hand.size);
    console.log(`   After hand: ${hand.size - 1} BB stack`);
  }

  console.log();
}

/**
 * Example 6: Dynamic Bankroll Adjustment
 */
async function bankrollAdjustmentExample(agent: Agent) {
  console.log('💰 Bankroll Adjustment Simulation\n');

  const metrics = await agent.getMetrics();

  console.log('Initial bankroll metrics:');
  console.log(`   Value: ${metrics.valueInUSDC} USDC`);
  console.log(`   Buyins remaining: ${metrics.buyinsRemaining.toFixed(1)}`);
  console.log(`   Risk of ruin: ${(metrics.riskOfRuin * 100).toFixed(1)}%`);
  console.log(`   Status: ${metrics.status}`);
  console.log();

  // Simulate a win (add to bankroll)
  const winAmount = BigInt('2000000000000000000'); // 2 WETH
  agent.currentBankroll += winAmount;
  (agent as any).bankrollManager.updateBankroll(agent.currentBankroll);

  console.log('After tournament win (+2 WETH):');
  const metricsAfter = await agent.getMetrics();
  console.log(`   Value: ${metricsAfter.valueInUSDC} USDC`);
  console.log(`   Buyins remaining: ${metricsAfter.buyinsRemaining.toFixed(1)}`);
  console.log(`   ROI: ${metricsAfter.totalROI.toFixed(2)}%`);
  console.log();
}

/**
 * Example 7: Tournament Exit
 */
async function exitTournamentExample(agent: Agent) {
  console.log('🏁 Tournament Exit\n');

  // Simulate exiting in 5th place with a prize
  const finishPosition = 5;
  const finalStack = BigInt('0'); // All-in
  const prize = BigInt('2500000000000000000'); // 2.5 WETH prize

  agent.exitTournament(finishPosition, finalStack, prize);
  console.log();

  const finalStatus = await agent.getStatus();
  console.log('Final bankroll status:');
  console.log(`   Current: ${finalStatus.bankroll.inUSDC} USDC`);
  console.log(`   Buyins remaining: ${finalStatus.bankroll.buyinsRemaining}`);
  console.log(`   Status: ${finalStatus.bankroll.status}`);
}

/**
 * Example 8: Multi-Tournament Simulation
 */
async function multiTournamentSimulation(agent: Agent) {
  console.log('\n🎯 Multi-Tournament Simulation\n');
  console.log('Simulating 5 tournament entries...\n');

  const tournaments = [
    { name: 'Tournament 1', buyin: BigInt('1000000000000000000'), prize: BigInt('2500000000000000000') },
    { name: 'Tournament 2', buyin: BigInt('1000000000000000000'), prize: BigInt('0') }, // Bust
    { name: 'Tournament 3', buyin: BigInt('1000000000000000000'), prize: BigInt('1500000000000000000') },
    { name: 'Tournament 4', buyin: BigInt('1000000000000000000'), prize: BigInt('3000000000000000000') },
    { name: 'Tournament 5', buyin: BigInt('1000000000000000000'), prize: BigInt('1000000000000000000') },
  ];

  for (const t of tournaments) {
    const tournament: Tournament = {
      id: `tournament-${tournaments.indexOf(t)}`,
      name: t.name,
      chain: 'monad',
      startTime: Date.now(),
      initialBlind: BigInt('25'),
      smallBlind: BigInt('25'),
      bigBlind: BigInt('50'),
      blindLevel: 1,
      blindIncreaseInterval: 600000,
      totalPlayers: 50,
      playersRemaining: 50,
      playerPositions: new Map(),
      entryFee: t.buyin,
      prizePool: BigInt('0'),
      phase: 'playing',
      roundNumber: 0,
      tableName: 'Table',
    };

    console.log(`${t.name}: Entry fee ${t.buyin.toString()}`);

    const joined = await agent.joinTournament(tournament, t.buyin);

    if (joined) {
      agent.exitTournament(Math.floor(Math.random() * 50) + 1, BigInt(0), t.prize);
    }

    const status = await agent.getStatus();
    console.log(`   After: ${status.bankroll.inUSDC} USDC, ${status.bankroll.buyinsRemaining} buyins\n`);
  }
}

/**
 * Example 9: Export Agent Configuration (for forking)
 */
async function exportAgentExample(agent: Agent) {
  console.log('\n💾 Exporting Agent Configuration\n');

  const exported = await agent.toJSON();

  console.log('Agent configuration (JSON):');
  console.log(JSON.stringify(exported, (key, value) => {
    if (typeof value === 'bigint') {
      return value.toString();
    }
    return value;
  }, 2));
}

/**
 * Main: Run all examples
 */
async function main() {
  try {
    console.log('🎯 Arena Agent Template Examples\n');
    console.log('='.repeat(60) + '\n');

    // Create agent
    const agent = await createAgentExample();

    // Check status
    await checkStatusExample(agent);
    console.log('='.repeat(60) + '\n');

    // Join tournament
    const tournament = await joinTournamentExample(agent);
    console.log('='.repeat(60) + '\n');

    // Get strategy recommendation
    await strategyRecommendationExample(agent);
    console.log('='.repeat(60) + '\n');

    // Play hands
    await playTournamentExample(agent);
    console.log('='.repeat(60) + '\n');

    // Bankroll adjustment
    await bankrollAdjustmentExample(agent);
    console.log('='.repeat(60) + '\n');

    // Exit tournament
    await exitTournamentExample(agent);
    console.log('='.repeat(60) + '\n');

    // Multi-tournament
    await multiTournamentSimulation(agent);
    console.log('='.repeat(60) + '\n');

    // Export
    await exportAgentExample(agent);

    console.log('\n✅ All Arena agent examples completed!');
  } catch (error) {
    console.error('Error:', error);
    process.exit(1);
  }
}

export {
  createAgentExample,
  checkStatusExample,
  joinTournamentExample,
  strategyRecommendationExample,
  playTournamentExample,
  bankrollAdjustmentExample,
  exitTournamentExample,
  multiTournamentSimulation,
  exportAgentExample,
};
export default main;

if (require.main === module) {
  main().catch(console.error);
}
