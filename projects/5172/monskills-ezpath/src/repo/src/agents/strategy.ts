/**
 * Strategy Engine
 * Determines optimal strategy based on bankroll, risk, and game conditions
 */

import { BankrollMetrics, StrategyMode, StrategyRecommendation, DecisionContext } from './types';

/**
 * Strategy configuration for each mode
 */
const STRATEGY_CONFIG: Record<
  StrategyMode,
  {
    description: string;
    minBankrollBuyins: number;
    maxBankrollBuyins: number;
    aggressiveness: number; // 0-1
    riskTolerance: number; // 0-1
    stkMultiplier: number; // Stack size multiplier
  }
> = {
  aggressive: {
    description: 'Play wide ranges, apply pressure, take calculated risks',
    minBankrollBuyins: 20,
    maxBankrollBuyins: 50,
    aggressiveness: 0.8,
    riskTolerance: 0.7,
    stkMultiplier: 1.5,
  },
  balanced: {
    description: 'Standard poker strategy, balanced aggression and caution',
    minBankrollBuyins: 15,
    maxBankrollBuyins: 100,
    aggressiveness: 0.5,
    riskTolerance: 0.4,
    stkMultiplier: 1.0,
  },
  conservative: {
    description: 'Tight ranges, minimal risk, solid fundamentals only',
    minBankrollBuyins: 5,
    maxBankrollBuyins: 50,
    aggressiveness: 0.2,
    riskTolerance: 0.1,
    stkMultiplier: 0.7,
  },
  adaptive: {
    description: 'Adjusts strategy based on game conditions and bankroll',
    minBankrollBuyins: 1,
    maxBankrollBuyins: 100,
    aggressiveness: 0.5,
    riskTolerance: 0.5,
    stkMultiplier: 1.0,
  },
};

/**
 * Strategy Engine
 */
export class StrategyEngine {
  /**
   * Recommend strategy based on bankroll metrics
   */
  static recommendStrategy(
    metrics: BankrollMetrics,
    skillLevel: string,
    currentStrategy: StrategyMode
  ): StrategyRecommendation {
    const bankrollHealth = Math.min(metrics.buyinsRemaining / 20, 1);

    // Determine optimal strategy
    let recommended: StrategyMode;
    let confidence = 0.5;

    if (metrics.status === 'critical' || metrics.status === 'bust') {
      // Must be conservative when in trouble
      recommended = 'conservative';
      confidence = 1.0;
    } else if (
      metrics.buyinsRemaining > 30 &&
      metrics.riskOfRuin < 0.05 &&
      skillLevel === 'advanced'
    ) {
      // Can be aggressive when healthy
      recommended = 'aggressive';
      confidence = 0.8;
    } else if (metrics.buyinsRemaining > 20 && metrics.riskOfRuin < 0.15) {
      // Balanced when moderate
      recommended = 'balanced';
      confidence = 0.7;
    } else if (metrics.buyinsRemaining < 10) {
      // Conservative when low
      recommended = 'conservative';
      confidence = 0.9;
    } else {
      // Default to adaptive
      recommended = 'adaptive';
      confidence = 0.6;
    }

    return {
      currentStrategy,
      recommendedStrategy: recommended,
      confidence,
      bankrollHealth,
      riskOfRuin: metrics.riskOfRuin,
      tableCondition: 'balanced', // Would be determined by game analysis
      opponentSkill: 'average', // Would be determined by opponent analysis
      suggestions: this.getSuggestions(recommended, metrics),
      warningFlags: this.getWarnings(metrics),
      reasoning: this.getReasoning(recommended, metrics),
    };
  }

  /**
   * Get strategy suggestions
   */
  private static getSuggestions(
    strategy: StrategyMode,
    metrics: BankrollMetrics
  ): string[] {
    const suggestions: string[] = [];

    const config = STRATEGY_CONFIG[strategy];

    if (metrics.buyinsRemaining < config.minBankrollBuyins) {
      suggestions.push(`Build bankroll to ${config.minBankrollBuyins}+ buyins before playing high stakes`);
    }

    switch (strategy) {
      case 'aggressive':
        suggestions.push('Open more hands from late position');
        suggestions.push('3-bet more frequently pre-flop');
        suggestions.push('Play more marginal hands in position');
        suggestions.push('Apply continuous pressure at tables');
        break;

      case 'balanced':
        suggestions.push('Follow standard poker fundamentals');
        suggestions.push('Adjust to table dynamics');
        suggestions.push('Mix up your play to avoid predictability');
        suggestions.push('Focus on value and position');
        break;

      case 'conservative':
        suggestions.push('Play only strong hands');
        suggestions.push('Avoid marginal situations');
        suggestions.push('Wait for premium hands');
        suggestions.push('Minimize variance');
        break;

      case 'adaptive':
        suggestions.push('Observe table conditions before committing');
        suggestions.push('Adjust aggression based on opponents');
        suggestions.push('Switch gears as needed');
        suggestions.push('Keep bankroll growth consistent');
        break;
    }

    return suggestions;
  }

  /**
   * Get warning flags
   */
  private static getWarnings(metrics: BankrollMetrics): string[] {
    const warnings: string[] = [];

    if (metrics.riskOfRuin > 0.5) {
      warnings.push('⚠️  Risk of ruin is HIGH. Consider taking a break.');
    }

    if (metrics.buyinsRemaining < 5) {
      warnings.push('⚠️  Critical bankroll level. Only play 0.5-1BB games.');
    }

    if (metrics.status === 'bust') {
      warnings.push('🚨 Bankroll below minimum. STOP playing immediately.');
    }

    if (metrics.buyinsRemaining > 50) {
      warnings.push('ℹ️  Bankroll is very healthy. Can afford to play higher stakes.');
    }

    return warnings;
  }

  /**
   * Get reasoning for recommendation
   */
  private static getReasoning(strategy: StrategyMode, metrics: BankrollMetrics): string {
    const buyins = metrics.buyinsRemaining.toFixed(1);
    const ror = (metrics.riskOfRuin * 100).toFixed(1);

    switch (strategy) {
      case 'aggressive':
        return `With ${buyins} buyins and RoR of ${ror}%, your bankroll is strong enough to play aggressively and maximize expected value.`;

      case 'balanced':
        return `With ${buyins} buyins and RoR of ${ror}%, a balanced approach maximizes long-term growth while managing risk.`;

      case 'conservative':
        return `With only ${buyins} buyins and RoR of ${ror}%, play conservatively to minimize variance and protect your bankroll.`;

      case 'adaptive':
        return `With ${buyins} buyins and RoR of ${ror}%, adapt your strategy to table conditions and opponents.`;

      default:
        return 'Unable to determine strategy.';
    }
  }

  /**
   * Make game decision given context
   */
  static makeGameDecision(context: DecisionContext): {
    action: 'fold' | 'check' | 'call' | 'raise' | 'all-in';
    confidence: number;
    reasoning: string;
  } {
    const aggressiveness = STRATEGY_CONFIG[context.strategy.recommendedStrategy].aggressiveness;

    // Simplified decision logic
    const stackInBuyins = context.stackInBuyins;
    const potOdds = context.potOdds;

    // If stack is critical, only play premium hands
    if (stackInBuyins < 3 && context.metrics.status === 'critical') {
      return {
        action: 'fold',
        confidence: 0.9,
        reasoning: 'Critical stack. Only push with premium hands.',
      };
    }

    // If pot odds are good and hand strength is decent, call
    if (potOdds > 2 && context.position !== 'early') {
      return {
        action: 'call',
        confidence: 0.7,
        reasoning: 'Positive pot odds. Good call opportunity.',
      };
    }

    // If aggressive and in position, consider raising
    if (aggressiveness > 0.6 && context.position === 'button') {
      return {
        action: 'raise',
        confidence: 0.6,
        reasoning: 'Late position with deep stack. Aggressive raise.',
      };
    }

    // Default: fold
    return {
      action: 'fold',
      confidence: 0.5,
      reasoning: 'Marginal situation. Fold for simplicity.',
    };
  }

  /**
   * Calculate optimal buyin amount for tournament
   */
  static calculateOptimalBuyin(
    bankroll: bigint,
    _strategy: StrategyMode,
    minBuyin: bigint,
    maxBuyin: bigint
  ): bigint {
    // Buyin should be 1-2% of bankroll (conservative)
    const one_percent = bankroll / BigInt(100);
    const optimalBuyin = one_percent * BigInt(2);

    // Clamp to min/max
    if (optimalBuyin < minBuyin) return minBuyin;
    if (optimalBuyin > maxBuyin) return maxBuyin;

    return optimalBuyin;
  }

  /**
   * Calculate session length recommendation
   */
  static recommendSessionLength(
    metrics: BankrollMetrics,
    skillLevel: string
  ): number {
    // In poor form, shorter sessions
    if (metrics.status === 'critical') {
      return 2 * 3600000; // 2 hours
    }

    // In good form, longer sessions
    if (metrics.status === 'healthy' && skillLevel === 'advanced') {
      return 8 * 3600000; // 8 hours
    }

    // Default
    return 4 * 3600000; // 4 hours
  }

  /**
   * Evaluate hand strength (simplified)
   */
  static evaluateHandStrength(hand: string): number {
    // Simplified hand evaluation
    // In production, this would be more sophisticated

    const handRanks: Record<string, number> = {
      'AA': 1.0,
      'KK': 0.95,
      'QQ': 0.9,
      'JJ': 0.85,
      'TT': 0.8,
      '99': 0.75,
      '88': 0.7,
      '77': 0.65,
      'AK': 0.85,
      'AQ': 0.75,
      'AJ': 0.65,
      'AT': 0.55,
    };

    return handRanks[hand] || 0.5;
  }
}

export default StrategyEngine;
