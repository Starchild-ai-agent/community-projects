/**
 * Arena Agent
 * Complete poker-style competition agent with bankroll management and strategy
 *
 * Features:
 * - Real-time bankroll valuation via EZ-Path
 * - Risk of ruin calculations
 * - Dynamic strategy selection
 * - Tournament participation logic
 * - Performance tracking
 */

import { ArenaAgent, AgentConfig, Tournament, TournamentEntry, DecisionContext, BankrollMetrics, StrategyRecommendation } from './types';
import BankrollManager from './bankroll-manager';
import StrategyEngine from './strategy';

/**
 * Arena Agent Implementation
 */
export class Agent implements ArenaAgent {
  // Agent properties
  id: string;
  name: string;
  address: `0x${string}`;
  chain: 'base' | 'monad';
  bankrollToken: `0x${string}`;
  initialBankroll: bigint;
  currentBankroll: bigint;
  minimumBankroll: bigint;

  // Strategy
  skillLevel: 'beginner' | 'intermediate' | 'advanced' | 'expert';
  strategy: 'aggressive' | 'balanced' | 'conservative' | 'adaptive';
  aggressivenessLevel: number;
  riskTolerance: number;
  targetROI: number;

  // Timestamps
  createdAt: number;
  updatedAt: number;
  metadata?: Record<string, any>;

  // Internal state
  private bankrollManager: BankrollManager;
  private tournamentEntry?: TournamentEntry;

  constructor(config: AgentConfig) {
    this.id = config.id;
    this.name = config.name;
    this.address = config.address;
    this.chain = config.chain;
    this.bankrollToken = config.bankrollToken;
    this.initialBankroll = config.initialBankroll;
    this.currentBankroll = config.initialBankroll;
    this.minimumBankroll = config.minimumBankroll;

    this.skillLevel = config.skillLevel;
    this.strategy = config.strategy;
    this.aggressivenessLevel = config.aggressivenessLevel || 0.5;
    this.riskTolerance = config.riskTolerance || 0.4;
    this.targetROI = config.targetROI || 0.2; // 20% monthly target

    this.createdAt = Date.now();
    this.updatedAt = Date.now();

    this.bankrollManager = new BankrollManager(this);
  }

  /**
   * Join a tournament
   */
  async joinTournament(tournament: Tournament, buyin: bigint): Promise<boolean> {
    console.log(`\n[${this.name}] Evaluating tournament entry...`);

    // Check if we can afford it
    if (!this.bankrollManager.canAffordBuyin(buyin)) {
      console.log(`❌ Cannot afford buyin of ${buyin.toString()}`);
      return false;
    }

    // Check bankroll management rules
    const shouldPlay = this.bankrollManager.shouldPlayTournament(
      buyin,
      tournament.totalPlayers
    );

    if (!shouldPlay) {
      console.log(`⚠️  Tournament is too risky relative to bankroll`);
      return false;
    }

    // Get current metrics
    const metrics = await this.bankrollManager.getMetrics();
    console.log(`✅ Bankroll metrics:`);
    console.log(`   Buyins remaining: ${metrics.buyinsRemaining.toFixed(1)}`);
    console.log(`   Risk of ruin: ${(metrics.riskOfRuin * 100).toFixed(1)}%`);
    console.log(`   Status: ${metrics.status}`);

    // Deduct buyin from bankroll
    this.currentBankroll -= buyin;
    this.bankrollManager.updateBankroll(this.currentBankroll);

    // Set tournament state
    this.tournamentEntry = {
      tournamentId: tournament.id,
      agentId: this.id,
      entryFee: buyin,
      initialStack: buyin, // Stack = buyin initially
      currentStack: buyin,
      position: 0,
      handsPlayed: 0,
      handsWon: 0,
      handsLost: 0,
      totalWinnings: BigInt(0),
      totalLosses: BigInt(0),
      isActive: true,
      joinedAt: Date.now(),
      lastActionAt: Date.now(),
    };

    console.log(`✅ Joined tournament: ${tournament.name}`);
    console.log(`   Buyin: ${buyin.toString()}`);
    console.log(`   Initial stack: ${buyin.toString()}`);

    return true;
  }

  /**
   * Exit tournament (busted or cashed)
   */
  exitTournament(
    finishPosition: number,
    _finalStack: bigint,
    prize: bigint
  ): void {
    if (!this.tournamentEntry) {
      console.warn('Not in a tournament');
      return;
    }

    console.log(`\n[${this.name}] Tournament Exit`);
    console.log(`   Finish position: ${finishPosition}`);
    console.log(`   Prize: ${prize.toString()}`);

    const profit = prize - this.tournamentEntry.entryFee;
    const roi = Number(profit) / Number(this.tournamentEntry.entryFee);

    console.log(`   Profit: ${profit.toString()} (${(roi * 100).toFixed(1)}%)`);

    // Update bankroll
    this.currentBankroll += prize;
    this.bankrollManager.updateBankroll(this.currentBankroll);
    this.bankrollManager.recordTournamentResult(
      this.tournamentEntry.tournamentId,
      this.tournamentEntry.entryFee,
      profit
    );

    // Update entry
    this.tournamentEntry.isActive = false;
    this.tournamentEntry.finishPosition = finishPosition;
    this.tournamentEntry.exitedAt = Date.now();

    this.tournamentEntry = undefined;
  }

  /**
   * Get strategy recommendation
   */
  async getStrategyRecommendation(): Promise<StrategyRecommendation> {
    const metrics = await this.bankrollManager.getMetrics();
    return StrategyEngine.recommendStrategy(metrics, this.skillLevel, this.strategy);
  }

  /**
   * Update strategy if recommended
   */
  async updateStrategyIfNeeded(): Promise<boolean> {
    const recommendation = await this.getStrategyRecommendation();

    if (
      recommendation.recommendedStrategy !== this.strategy &&
      recommendation.confidence > 0.7
    ) {
      console.log(`\n[${this.name}] Strategy update:`);
      console.log(`   Current: ${this.strategy}`);
      console.log(`   Recommended: ${recommendation.recommendedStrategy}`);
      console.log(`   Confidence: ${(recommendation.confidence * 100).toFixed(0)}%`);
      console.log(`   Reason: ${recommendation.reasoning}`);

      this.strategy = recommendation.recommendedStrategy;
      return true;
    }

    return false;
  }

  /**
   * Make game decision given context
   */
  makeDecision(context: Partial<DecisionContext>) {
    if (!context.strategy || !context.metrics) {
      return {
        action: 'fold' as const,
        confidence: 0.5,
        reasoning: 'Insufficient context for decision',
      };
    }

    return StrategyEngine.makeGameDecision(context as DecisionContext);
  }

  /**
   * Get bankroll metrics
   */
  async getMetrics(): Promise<BankrollMetrics> {
    return this.bankrollManager.getMetrics();
  }

  /**
   * Get agent status
   */
  async getStatus() {
    const metrics = await this.bankrollManager.getMetrics();
    const recommendation = await this.getStrategyRecommendation();

    return {
      agent: {
        id: this.id,
        name: this.name,
        address: this.address,
        skillLevel: this.skillLevel,
        currentStrategy: this.strategy,
      },
      bankroll: {
        current: this.currentBankroll.toString(),
        initial: this.initialBankroll.toString(),
        inUSDC: metrics.valueInUSDC,
        buyinsRemaining: metrics.buyinsRemaining.toFixed(1),
        status: metrics.status,
      },
      risk: {
        riskOfRuin: (metrics.riskOfRuin * 100).toFixed(1) + '%',
        healthScore: metrics.healthScore,
        trend: this.bankrollManager['getRecentTrend'](),
      },
      strategy: {
        current: this.strategy,
        recommended: recommendation.recommendedStrategy,
        confidence: (recommendation.confidence * 100).toFixed(0) + '%',
        reasoning: recommendation.reasoning,
      },
      tournament: this.tournamentEntry
        ? {
          id: this.tournamentEntry.tournamentId,
          stack: this.tournamentEntry.currentStack.toString(),
          handsPlayed: this.tournamentEntry.handsPlayed,
          active: this.tournamentEntry.isActive,
        }
        : null,
      actions: metrics.recommendedAction,
    };
  }

  /**
   * Simulate a hand
   */
  async playHand(handType: string, stackSizeInBuyins: number): Promise<void> {
    if (!this.tournamentEntry) {
      console.warn('Agent is not in a tournament');
      return;
    }

    const handStrength = StrategyEngine.evaluateHandStrength(handType);

    console.log(`\n[${this.name}] Playing hand ${handType}`);
    console.log(`   Strength: ${(handStrength * 100).toFixed(0)}%`);
    console.log(`   Stack: ${stackSizeInBuyins.toFixed(1)} BB`);

    this.tournamentEntry.handsPlayed++;

    // Simulate outcome (very simplified)
    const winChance = handStrength * 0.8; // 80% win rate for strong hands
    const won = Math.random() < winChance;

    if (won) {
      this.tournamentEntry.handsWon++;
      this.tournamentEntry.currentStack += BigInt(100); // Won 100 chips
      console.log(`   ✅ Won hand`);
    } else {
      this.tournamentEntry.handsLost++;
      this.tournamentEntry.currentStack -= BigInt(50); // Lost 50 chips
      console.log(`   ❌ Lost hand`);
    }

    this.tournamentEntry.lastActionAt = Date.now();
  }

  /**
   * Check if should quit tournament early
   */
  shouldQuitTournament(): boolean {
    if (!this.tournamentEntry) return false;

    const recommendation = this.strategy;

    // Quit if in critical condition and playing conservative
    if (recommendation === 'conservative' && this.tournamentEntry.handsLost > 5) {
      return true;
    }

    return false;
  }

  /**
   * Export agent state as JSON
   */
  async toJSON() {
    return {
      agent: {
        id: this.id,
        name: this.name,
        address: this.address,
        chain: this.chain,
        skillLevel: this.skillLevel,
        strategy: this.strategy,
      },
      bankroll: {
        current: this.currentBankroll.toString(),
        initial: this.initialBankroll.toString(),
        minimum: this.minimumBankroll.toString(),
      },
      metrics: await this.getMetrics(),
      status: await this.getStatus(),
      createdAt: this.createdAt,
      updatedAt: this.updatedAt,
    };
  }
}

export default Agent;
