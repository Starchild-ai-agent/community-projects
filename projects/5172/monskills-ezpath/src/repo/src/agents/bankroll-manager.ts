/**
 * Bankroll Manager
 * Handles bankroll tracking, valuation, and risk calculations for Arena agents
 */

import { getPrice } from '../index';
import {
  ArenaAgent,
  BankrollMetrics,
  BankrollStatus,
  HistoricalRecord,
} from './types';

/**
 * Bankroll Manager class
 * Tracks and analyzes agent bankroll
 */
export class BankrollManager {
  private agent: ArenaAgent;
  private history: HistoricalRecord[] = [];

  constructor(agent: ArenaAgent) {
    this.agent = agent;
    this.recordSnapshot();
  }

  /**
   * Record current bankroll snapshot
   */
  private recordSnapshot() {
    // TODO: Get current price from cache or API
    // For now, just record the raw value
    this.history.push({
      timestamp: Date.now(),
      bankroll: this.agent.currentBankroll,
      valueInUSDC: this.estimateUSDCValue(),
    });
  }

  /**
   * Update agent's current bankroll
   */
  updateBankroll(newAmount: bigint) {
    this.agent.currentBankroll = newAmount;
    this.agent.updatedAt = Date.now();
    this.recordSnapshot();
  }

  /**
   * Get current bankroll metrics
   */
  async getMetrics(): Promise<BankrollMetrics> {
    const valueInUSDC = await this.valuateBankroll();
    const buyinsRemaining = this.calculateBuyinsRemaining();
    const riskOfRuin = this.calculateRiskOfRuin(buyinsRemaining);
    const status = this.determineBankrollStatus(buyinsRemaining, riskOfRuin);

    return {
      value: this.agent.currentBankroll,
      valueInUSDC,
      buyinsRemaining,
      riskOfRuin,
      expectedValue: this.calculateExpectedValue(),
      peakValue: this.getPeakValue(),
      lowestValue: this.getLowestValue(),
      dailyChange: this.calculateDailyChange(),
      totalROI: this.calculateTotalROI(),
      status,
      healthScore: this.calculateHealthScore(buyinsRemaining, riskOfRuin),
      recommendedAction: this.getRecommendedAction(status, buyinsRemaining),
    };
  }

  /**
   * Valuate bankroll in USDC
   */
  private async valuateBankroll(): Promise<string> {
    try {
      // Use getPrice to get current valuation
      const result = await getPrice(
        this.agent.chain,
        this.agent.bankrollToken,
        '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // USDC
        this.agent.currentBankroll.toString()
      );

      if ('price' in result) {
        return result.price;
      }
    } catch (error) {
      console.warn('Failed to valuate bankroll:', error);
    }

    return this.estimateUSDCValue();
  }

  /**
   * Estimate USDC value (fallback)
   */
  private estimateUSDCValue(): string {
    // Rough estimate based on agent configuration
    // In production, this would be derived from actual price data
    return (Number(this.agent.currentBankroll) / 1e18).toFixed(2);
  }

  /**
   * Calculate number of buyins remaining
   */
  private calculateBuyinsRemaining(): number {
    // Assume 1 buyin = 1 unit of bankroll token
    // In production, would use actual buyin amounts from tournaments
    return Number(this.agent.currentBankroll) / Number(this.agent.initialBankroll);
  }

  /**
   * Calculate risk of ruin
   * Based on bankroll in buyins and assumed win rate
   */
  private calculateRiskOfRuin(bankrollInBuyins: number): number {
    // Simplified Kelly Criterion-based RoR calculation
    // winRate estimation available via estimateWinRate() but using fixed thresholds for simplicity

    if (bankrollInBuyins < 1) return 0.99; // Nearly certain bust
    if (bankrollInBuyins < 5) return 0.7;
    if (bankrollInBuyins < 10) return 0.4;
    if (bankrollInBuyins < 20) return 0.15;
    if (bankrollInBuyins < 30) return 0.05;
    return 0.01;
  }

  /**
   * Estimate agent's win rate based on skill level
   */
  private estimateWinRate(): number {
    // Base win rate assumptions by skill level
    const baseWinRates: Record<string, number> = {
      beginner: 0.48,
      intermediate: 0.51,
      advanced: 0.54,
      expert: 0.58,
    };

    return baseWinRates[this.agent.skillLevel] || 0.50;
  }

  /**
   * Determine bankroll status
   */
  private determineBankrollStatus(
    buyinsRemaining: number,
    riskOfRuin: number
  ): BankrollStatus {
    if (Number(this.agent.currentBankroll) <= Number(this.agent.minimumBankroll)) {
      return 'bust';
    }
    if (buyinsRemaining < 5 || riskOfRuin > 0.5) {
      return 'critical';
    }
    if (buyinsRemaining < 10 || riskOfRuin > 0.2) {
      return 'cautious';
    }
    return 'healthy';
  }

  /**
   * Calculate expected value over time
   */
  private calculateExpectedValue(): string {
    const winRate = this.estimateWinRate();
    const hourlyRate = 0.1; // 10% of buyin per hour (assumption)
    const expectedHourly = Number(this.agent.initialBankroll) * hourlyRate * (winRate - 0.5);

    return expectedHourly.toFixed(2);
  }

  /**
   * Get peak bankroll value
   */
  private getPeakValue(): bigint {
    if (this.history.length === 0) return this.agent.initialBankroll;

    return this.history.reduce((max, record) =>
      record.bankroll > max ? record.bankroll : max
    , this.agent.initialBankroll);
  }

  /**
   * Get lowest bankroll value
   */
  private getLowestValue(): bigint {
    if (this.history.length === 0) return this.agent.currentBankroll;

    return this.history.reduce((min, record) =>
      record.bankroll < min ? record.bankroll : min
    , this.agent.currentBankroll);
  }

  /**
   * Calculate daily P&L
   */
  private calculateDailyChange(): string {
    const oneDayAgo = Date.now() - 86400000;
    const historicalRecord = this.history.find((r) => r.timestamp <= oneDayAgo);

    if (!historicalRecord) {
      return '0.00';
    }

    const change = Number(this.agent.currentBankroll - historicalRecord.bankroll) / 1e18;
    return change.toFixed(2);
  }

  /**
   * Calculate total ROI
   */
  private calculateTotalROI(): number {
    const current = Number(this.agent.currentBankroll) / 1e18;
    const initial = Number(this.agent.initialBankroll) / 1e18;

    return ((current - initial) / initial) * 100;
  }

  /**
   * Calculate health score (0-100)
   */
  private calculateHealthScore(buyinsRemaining: number, riskOfRuin: number): number {
    // More buyins = higher score
    const buyinScore = Math.min(buyinsRemaining / 30, 1) * 50;

    // Lower RoR = higher score
    const rorScore = (1 - riskOfRuin) * 50;

    return Math.round(buyinScore + rorScore);
  }

  /**
   * Get recommended action based on status
   */
  private getRecommendedAction(status: BankrollStatus, buyinsRemaining: number): string {
    switch (status) {
      case 'bust':
        return 'RELOAD: Bankroll below minimum. Consider adding funds or taking a break.';
      case 'critical':
        return `CAUTIOUS: Only ${buyinsRemaining.toFixed(1)} buyins remaining. Play tight.`;
      case 'cautious':
        return `CAREFUL: ${buyinsRemaining.toFixed(1)} buyins remaining. Play ABC poker.`;
      case 'healthy':
        return `HEALTHY: ${buyinsRemaining.toFixed(1)} buyins. Play your strategy.`;
      default:
        return 'UNKNOWN';
    }
  }

  /**
   * Get historical data
   */
  getHistory(since?: number): HistoricalRecord[] {
    if (!since) return this.history;

    return this.history.filter((r) => r.timestamp >= since);
  }

  /**
   * Add tournament result to history
   */
  recordTournamentResult(
    tournamentId: string,
    buyin: bigint,
    profit: bigint
  ) {
    this.history.push({
      timestamp: Date.now(),
      bankroll: this.agent.currentBankroll,
      valueInUSDC: this.estimateUSDCValue(),
      tournamentId,
      buyin,
      profit,
      notes: `Tournament ${tournamentId.substring(0, 8)}...`,
    });
  }

  /**
   * Get bankroll trend (last 24 hours)
   */
  getRecentTrend(): 'up' | 'down' | 'flat' {
    const oneDayAgo = Date.now() - 86400000;
    const dayOldRecord = this.history.find((r) => r.timestamp <= oneDayAgo);

    if (!dayOldRecord) return 'flat';

    const change = this.agent.currentBankroll - dayOldRecord.bankroll;

    if (change > BigInt(0)) return 'up';
    if (change < BigInt(0)) return 'down';
    return 'flat';
  }

  /**
   * Simulate tournament buyins
   */
  canAffordBuyin(buyinAmount: bigint): boolean {
    return this.agent.currentBankroll >= buyinAmount;
  }

  /**
   * Check if agent should play in tournament
   */
  shouldPlayTournament(buyinAmount: bigint, expectedFieldSize: number): boolean {
    if (!this.canAffordBuyin(buyinAmount)) {
      return false; // Can't afford it
    }

    const buyinRatio =
      Number(buyinAmount) / Number(this.agent.currentBankroll);

    // Only play if buyin is <5% of bankroll (conservative)
    if (buyinRatio > 0.05) {
      return false; // Too risky
    }

    // Check expected value
    const expectedWinChance = 1 / expectedFieldSize;
    const expectedEV = expectedWinChance; // Very rough

    return expectedEV > 0;
  }

  /**
   * Export metrics as JSON
   */
  async toJSON() {
    const metrics = await this.getMetrics();

    return {
      agent: {
        id: this.agent.id,
        name: this.agent.name,
        skillLevel: this.agent.skillLevel,
      },
      metrics,
      trend: this.getRecentTrend(),
      history: this.history.slice(-24), // Last 24 records
    };
  }
}

export default BankrollManager;
