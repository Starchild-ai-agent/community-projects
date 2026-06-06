# Arena Agent Framework

Complete guide for building poker-style competition agents using the EZ-Path MONSKILLS plugin.

## Overview

The Arena Agent Framework provides:

- **Bankroll Management** — Real-time valuation via EZ-Path pricing
- **Risk Calculations** — Risk of ruin, optimal buyin sizing
- **Strategy Engine** — Dynamic strategy selection based on bankroll
- **Tournament Integration** — Join, play, and exit tournaments
- **Performance Tracking** — Historical data and analytics

## Quick Start

### 1. Create an Agent

```typescript
import { Agent } from '@infiniteezverse/monskills-ezpath/dist/agents';

const agent = new Agent({
  id: 'my-agent-001',
  name: 'AlphaPoker',
  address: '0x1234567890123456789012345678901234567890',
  chain: 'monad',
  bankrollToken: '0x4200000000000000000000000000000000000006', // WETH
  initialBankroll: BigInt('10000000000000000000'), // 10 WETH
  minimumBankroll: BigInt('500000000000000000'), // 0.5 WETH
  skillLevel: 'advanced',
  strategy: 'balanced',
  aggressivenessLevel: 0.6,
  riskTolerance: 0.5,
  targetROI: 0.2, // 20% monthly
});
```

### 2. Check Status

```typescript
const status = await agent.getStatus();

console.log(`Bankroll: ${status.bankroll.inUSDC} USDC`);
console.log(`Buyins: ${status.bankroll.buyinsRemaining}`);
console.log(`Risk: ${status.risk.riskOfRuin}`);
console.log(`Strategy: ${status.strategy.recommended}`);
```

### 3. Join Tournament

```typescript
const tournament = {
  id: 'tournament-001',
  name: 'Friday Night',
  chain: 'monad',
  totalPlayers: 50,
  entryFee: BigInt('1000000000000000000'), // 1 WETH
  // ... other fields
};

const joined = await agent.joinTournament(tournament, tournament.entryFee);
```

### 4. Play & Exit

```typescript
// Play hands
await agent.playHand('AK', 20); // AK with 20 BB stack

// Exit tournament
agent.exitTournament(
  5,                                      // Finish position
  BigInt('0'),                           // Final stack
  BigInt('2500000000000000000')  // Prize (2.5 WETH)
);
```

## Agent Configuration

### Required Fields

```typescript
interface AgentConfig {
  id: string;                          // Unique agent ID
  name: string;                        // Display name
  address: '0x' + string;             // Wallet address
  chain: 'base' | 'monad';            // Chain to operate on
  bankrollToken: '0x' + string;       // Token for bankroll
  initialBankroll: bigint;             // Starting amount
  minimumBankroll: bigint;             // Bust-out threshold
  skillLevel: 'beginner' | 'intermediate' | 'advanced' | 'expert';
  strategy: 'aggressive' | 'balanced' | 'conservative' | 'adaptive';
}
```

### Optional Fields

```typescript
interface AgentConfig {
  aggressivenessLevel?: number;  // 0-1, default 0.5
  riskTolerance?: number;        // 0-1, default 0.4
  targetROI?: number;            // Default 0.2 (20%)
}
```

## Bankroll Management

### Get Current Metrics

```typescript
const metrics = await agent.getMetrics();

console.log(`Value: ${metrics.valueInUSDC}`);           // USDC valuation
console.log(`Buyins: ${metrics.buyinsRemaining}`);      // Number of buyins
console.log(`RoR: ${metrics.riskOfRuin}`);             // Risk of ruin (0-1)
console.log(`Status: ${metrics.status}`);              // healthy|cautious|critical|bust
console.log(`Health: ${metrics.healthScore}/100`);     // Overall health
```

### Bankroll Status Levels

| Status | Buyins | RoR | Meaning |
|--------|--------|-----|---------|
| **healthy** | 20+ | <5% | Safe to play normally |
| **cautious** | 10-20 | 5-20% | Play carefully |
| **critical** | 5-10 | 20-50% | Very risky |
| **bust** | <5 | >50% | Stop playing |

### Can Agent Afford Tournament?

```typescript
const buyin = BigInt('1000000000000000000');

// Check affordability
if (agent.bankrollManager.canAffordBuyin(buyin)) {
  // Bankroll > buyin
}

// Check bankroll management rules
const shouldPlay = agent.bankrollManager.shouldPlayTournament(
  buyin,
  50 // field size
);
```

### Record Tournament Results

```typescript
agent.bankrollManager.recordTournamentResult(
  'tournament-001',
  buyin,                    // Amount paid
  profit                    // Amount won - buyin
);
```

## Strategy Engine

### Get Strategy Recommendation

```typescript
const recommendation = await agent.getStrategyRecommendation();

console.log(`Current: ${recommendation.currentStrategy}`);
console.log(`Recommended: ${recommendation.recommendedStrategy}`);
console.log(`Confidence: ${recommendation.confidence}`); // 0-1

console.log('Suggestions:');
recommendation.suggestions.forEach(s => console.log(`  • ${s}`));

if (recommendation.warningFlags.length > 0) {
  console.log('Warnings:');
  recommendation.warningFlags.forEach(w => console.log(`  ⚠️  ${w}`));
}
```

### Strategy Modes

#### Aggressive
```typescript
strategy: 'aggressive'

// When to use:
// - Bankroll > 30 buyins
// - Risk of ruin < 5%
// - Advanced skill level

// Play style:
// - Wide opening ranges
// - Frequent 3-bets
// - Marginal situations OK
// - Variance is expected
```

#### Balanced
```typescript
strategy: 'balanced'

// When to use:
// - Bankroll 15-100 buyins
// - Risk of ruin 5-20%
// - Any skill level

// Play style:
// - Standard poker fundamentals
// - Mix aggression with caution
// - Adaptive to table
// - Steady growth
```

#### Conservative
```typescript
strategy: 'conservative'

// When to use:
// - Bankroll < 10 buyins
// - Risk of ruin > 20%
// - Building back up

// Play style:
// - Premium hands only
// - Minimize variance
// - Avoid marginal spots
// - Preserve bankroll
```

#### Adaptive
```typescript
strategy: 'adaptive'

// When to use:
// - Tournament conditions vary
// - Need flexibility
// - Mixed field skills

// Play style:
// - Adjust based on situation
// - Read opponents
// - Exploit weaknesses
// - Balance all factors
```

### Update Strategy Dynamically

```typescript
const updated = await agent.updateStrategyIfNeeded();

if (updated) {
  console.log(`Strategy updated to ${agent.strategy}`);
}
```

## Tournament Participation

### Join Tournament

```typescript
const joined = await agent.joinTournament(tournament, buyin);

if (!joined) {
  console.log('Could not join. Reasons:');
  // - Cannot afford buyin
  // - Bankroll management rules violated
  // - Risk of ruin too high
}
```

### Play Hands

```typescript
await agent.playHand('AK', 20); // Hand type, stack in BB

// Hand types supported:
// - Pocket pairs: 'AA', 'KK', 'QQ', etc.
// - Unsuited: 'AK', 'QJ', etc.
// - Suited: 'AS', 'KS', etc.
```

### Exit Tournament

```typescript
agent.exitTournament(
  finishPosition,  // Where agent finished (1-50)
  finalStack,      // Remaining chips (usually 0 if busted)
  prizeAmount      // Amount won
);
```

### Tournament Entry State

```typescript
interface TournamentEntry {
  tournamentId: string;
  agentId: string;
  entryFee: bigint;
  initialStack: bigint;
  currentStack: bigint;
  position: number;
  handsPlayed: number;
  handsWon: number;
  handsLost: number;
  totalWinnings: bigint;
  totalLosses: bigint;
  isActive: boolean;
  bustedAt?: number;
  finishPosition?: number;
  joinedAt: number;
  exitedAt?: number;
}
```

## Decision Making

### Get Game Decision

```typescript
const decision = agent.makeDecision({
  strategy: recommendation,
  metrics: metrics,
  position: 'late',        // early|middle|late|button
  stackInBuyins: 15,
  potOdds: 2.5,
  chipStack: BigInt('1500')
});

console.log(`Action: ${decision.action}`);        // fold|check|call|raise|all-in
console.log(`Confidence: ${decision.confidence}`); // 0-1
console.log(`Reason: ${decision.reasoning}`);
```

## Use Cases

### 1. Automated Tournament Agent

```typescript
// Create agent
const agent = new Agent(config);

// Join tournaments in loop
for (const tournament of tournaments) {
  const joined = await agent.joinTournament(tournament, buyin);
  
  if (joined) {
    // Play hands
    while (agent.tournamentEntry?.isActive) {
      const decision = agent.makeDecision(context);
      executeDecision(decision);
    }
    
    // Exit
    agent.exitTournament(position, finalStack, prize);
  }
}
```

### 2. Bankroll Simulator

```typescript
const agent = new Agent(config);

// Simulate 1000 hands
for (let i = 0; i < 1000; i++) {
  const result = simulateHand(agent.strategy);
  agent.currentBankroll += result.profit;
  (agent as any).bankrollManager.updateBankroll(agent.currentBankroll);
}

const metrics = await agent.getMetrics();
console.log(`Final bankroll: ${metrics.valueInUSDC}`);
console.log(`ROI: ${metrics.totalROI}%`);
```

### 3. Strategy A/B Test

```typescript
// Create two agents with different strategies
const aggressiveAgent = new Agent({ ...config, strategy: 'aggressive' });
const conservativeAgent = new Agent({ ...config, strategy: 'conservative' });

// Run same tournaments
const results = await runTournaments([aggressiveAgent, conservativeAgent]);

// Compare performance
console.log(`Aggressive ROI: ${results[0].roi}`);
console.log(`Conservative ROI: ${results[1].roi}`);
```

## Performance Tracking

### Get Agent History

```typescript
// Last 24 records
const history = agent.bankrollManager.getHistory();

// Since timestamp
const recent = agent.bankrollManager.getHistory(Date.now() - 86400000);

// Each record includes:
// - timestamp
// - bankroll
// - valueInUSDC
// - tournamentId (if applicable)
// - buyin / profit
```

### Bankroll Trend

```typescript
const trend = agent.bankrollManager.getRecentTrend();

// 'up' | 'down' | 'flat' (last 24 hours)
```

### Export Agent State

```typescript
const exported = await agent.toJSON();

// Includes:
// - Agent config
// - Current bankroll
// - Metrics
// - Status
// - Timestamps
```

## Examples

Complete working examples in `/examples/`:

- **`arena-agent-template.ts`** — Full Arena agent examples with 9 use cases

Run examples:

```bash
npm install
npx ts-node examples/arena-agent-template.ts
```

## Integration with EZ-Path

The Agent framework uses EZ-Path for real-time bankroll valuation:

```typescript
import { getPrice } from '@infiniteezverse/monskills-ezpath';

// Get WETH/USDC price
const price = await getPrice(
  'monad',
  '0x4200000000000000000000000000000000000006', // WETH
  '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // USDC
  agentBankrollAmount
);

// Price is now available for risk calculations
```

## Advanced Patterns

### Custom Risk Calculations

```typescript
class CustomAgent extends Agent {
  async getCustomRiskOfRuin(): Promise<number> {
    const metrics = await this.getMetrics();
    const winRate = estimateWinRateFromHistory();
    
    // Custom calculation
    return customRoRFormula(metrics.buyinsRemaining, winRate);
  }
}
```

### Strategy Overrides

```typescript
const recommendation = await agent.getStrategyRecommendation();

// Override recommendation
if (specialCondition) {
  agent.strategy = 'custom-strategy';
}

// Make decision
const decision = agent.makeDecision(context);
```

### Tournament Chains

```typescript
// Join multiple tournaments in sequence
for (const tournament of tournamentSchedule) {
  await agent.joinTournament(tournament, calculateOptimalBuyin(agent));
  
  // Play tournament...
  
  agent.exitTournament(position, finalStack, prize);
  
  // Check if should continue
  const metrics = await agent.getMetrics();
  if (metrics.status === 'bust') break;
}
```

## Troubleshooting

### Agent shows "bust" status but bankroll > minimum

**Cause:** Calculation issue or stale cache
**Solution:** Manually refresh metrics

```typescript
const metrics = await agent.getMetrics();
// Metrics are always calculated fresh
```

### Strategy not updating

**Cause:** Confidence threshold too high (>0.7)
**Solution:** Force update or lower threshold

```typescript
// Force update
agent.strategy = 'conservative';

// Or check confidence
if (recommendation.confidence > 0.5) {
  agent.strategy = recommendation.recommendedStrategy;
}
```

### Unrealistic tournament results

**Cause:** Simulation is simplified
**Solution:** Review `playHand()` logic

```typescript
// Current simulation:
// - Hand strength determines win probability
// - Fixed chip amounts per hand
// - No pot odds consideration

// For production: implement full game simulation
```

## Support

- 📖 Full code: https://github.com/infiniteezverse/monskills-ezpath/src/agents/
- 💬 Monad Discord: https://discord.gg/monad
- 🐦 Twitter: @infiniteezverse
- 📦 NPM: @infiniteezverse/monskills-ezpath
