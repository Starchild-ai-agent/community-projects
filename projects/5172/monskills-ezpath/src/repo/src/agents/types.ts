/**
 * Arena Agent Type Definitions
 * Complete type system for poker-style competition agents
 */

/**
 * Agent skill levels
 */
export type AgentSkillLevel = 'beginner' | 'intermediate' | 'advanced' | 'expert';

/**
 * Strategy modes
 */
export type StrategyMode = 'aggressive' | 'balanced' | 'conservative' | 'adaptive';

/**
 * Game states
 */
export type GamePhase = 'registration' | 'playing' | 'heads-up' | 'final-table' | 'winner';

/**
 * Bankroll status
 */
export type BankrollStatus = 'healthy' | 'cautious' | 'critical' | 'bust';

/**
 * Agent identity and configuration
 */
export interface ArenaAgent {
  id: string;
  name: string;
  address: `0x${string}`;
  chain: 'base' | 'monad';

  // Skill and strategy
  skillLevel: AgentSkillLevel;
  strategy: StrategyMode;

  // Bankroll management
  bankrollToken: `0x${string}`;
  initialBankroll: bigint;
  currentBankroll: bigint;
  minimumBankroll: bigint; // Bust-out threshold

  // Configuration
  aggressivenessLevel: number; // 0-1, affects bet sizing
  riskTolerance: number; // 0-1, affects position sizing
  targetROI: number; // Expected return percentage

  // Metadata
  createdAt: number;
  updatedAt: number;
  metadata?: Record<string, any>;
}

/**
 * Tournament game state
 */
export interface Tournament {
  id: string;
  name: string;
  chain: 'base' | 'monad';

  // Game structure
  startTime: number;
  endTime?: number;

  // Blind structure
  initialBlind: bigint;
  smallBlind: bigint;
  bigBlind: bigint;
  blindLevel: number;
  blindIncreaseInterval: number; // milliseconds

  // Players
  totalPlayers: number;
  playersRemaining: number;
  playerPositions: Map<string, number>; // Agent ID → chip stack

  // Prize pool
  entryFee: bigint;
  prizePool: bigint;

  // Game state
  phase: GamePhase;
  roundNumber: number;
  tableName: string;

  // Meta
  metadata?: Record<string, any>;
}

/**
 * Agent's tournament participation
 */
export interface TournamentEntry {
  tournamentId: string;
  agentId: string;
  entryFee: bigint;
  initialStack: bigint;
  currentStack: bigint;
  position: number; // Table position (0-8)

  // Session stats
  handsPlayed: number;
  handsWon: number;
  handsLost: number;
  totalWinnings: bigint;
  totalLosses: bigint;

  // Status
  isActive: boolean;
  bustedAt?: number;
  finishPosition?: number; // Final placement

  // Timestamps
  joinedAt: number;
  lastActionAt: number;
  exitedAt?: number;
}

/**
 * Bankroll metrics and analytics
 */
export interface BankrollMetrics {
  value: bigint; // Current value in base tokens
  valueInUSDC: string; // Human-readable USD value

  // Calculations
  buyinsRemaining: number; // How many buyins left
  riskOfRuin: number; // 0-1 probability of bust
  expectedValue: string; // EV calculation

  // Trends
  peakValue: bigint; // Highest value reached
  lowestValue: bigint; // Lowest value reached
  dailyChange: string; // Today's P&L
  totalROI: number; // Return on investment %

  // Status
  status: BankrollStatus;
  healthScore: number; // 0-100
  recommendedAction: string; // Suggestion for agent
}

/**
 * Strategy recommendation
 */
export interface StrategyRecommendation {
  currentStrategy: StrategyMode;
  recommendedStrategy: StrategyMode;
  confidence: number; // 0-1

  // Metrics driving recommendation
  bankrollHealth: number; // 0-1
  riskOfRuin: number; // 0-1
  tableCondition: 'tight' | 'loose' | 'balanced';
  opponentSkill: 'weak' | 'average' | 'strong';

  // Action items
  suggestions: string[];
  warningFlags: string[];

  // Explanation
  reasoning: string;
}

/**
 * Performance statistics
 */
export interface PerformanceStats {
  // Session stats
  sessionDuration: number; // milliseconds
  handsPlayed: number;

  // Win rate
  winRate: number; // Hands won / hands played
  roi: number; // Return on investment
  profitFactor: number; // Wins / losses

  // Bankroll impact
  sessionProfit: bigint;
  sessionProfitPercent: number;

  // Risk metrics
  maxLoss: bigint; // Biggest losing hand
  maxWin: bigint; // Biggest winning hand
  averagePot: bigint;

  // Consistency
  standardDeviation: number;
  sharpeRatio: number; // Risk-adjusted return

  // Meta
  calculatedAt: number;
}

/**
 * Historical record
 */
export interface HistoricalRecord {
  timestamp: number;
  bankroll: bigint;
  valueInUSDC: string;
  tournamentId?: string;
  buyin?: bigint;
  profit?: bigint;
  notes?: string;
}

/**
 * Agent decision context
 */
export interface DecisionContext {
  agent: ArenaAgent;
  tournament: Tournament;
  entry: TournamentEntry;
  metrics: BankrollMetrics;
  strategy: StrategyRecommendation;

  // Situation
  position: 'early' | 'middle' | 'late' | 'button' | 'small-blind' | 'big-blind';
  chipStack: bigint;
  stackInBuyins: number;
  potOdds: number;

  // Actions available
  canRaise: boolean;
  canCall: boolean;
  canCheck: boolean;
  canFold: boolean;
  canGoAllIn: boolean;
}

/**
 * Price quote for bankroll valuation
 */
export interface PriceQuote {
  chain: 'base' | 'monad';
  token: `0x${string}`;
  priceInUSDC: string;
  sources: string[];
  timestamp: number;
  requestId: string;
}

/**
 * Agent configuration options
 */
export interface AgentConfig {
  id: string;
  name: string;
  address: `0x${string}`;
  chain: 'base' | 'monad';
  bankrollToken: `0x${string}`;
  initialBankroll: bigint;
  minimumBankroll: bigint;
  skillLevel: AgentSkillLevel;
  strategy: StrategyMode;
  aggressivenessLevel?: number;
  riskTolerance?: number;
  targetROI?: number;
}
