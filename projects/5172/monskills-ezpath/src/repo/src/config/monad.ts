/**
 * Monad-Specific Configuration
 * RPC endpoints, contract addresses, and optimization settings for Monad chain
 */

export const MONAD_CONFIG = {
  // Chain identification
  chainId: 10143,
  name: 'Monad',
  nativeToken: 'MON',

  // RPC Endpoints (primary + fallbacks)
  rpc: {
    primary: 'https://mainnet.monad.xyz/rpc',
    fallbacks: [
      'https://rpc-monad.monadscan.io',
      'https://monad-rpc.publicnode.com',
      'https://monad.drpc.org',
    ],
  },

  // Block explorer
  blockExplorer: 'https://monadiscan.io',

  // Token addresses on Monad
  tokens: {
    MON: '0x0000000000000000000000000000000000000001', // Native
    USDC: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // Bridged from Base
    WMON: '0x0000000000000000000000000000000000000002', // Wrapped MON
    WETH: '0x4200000000000000000000000000000000000006', // Bridged from Base
    USDbC: '0x50c5725949A6F0c72EC20E08a6DE0146F30F1F75', // Bridged
    DAI: '0x6B175474E89094C44Da98b954EedeAC495271d0F', // Bridged
    USDT: '0xdAC17F958D2ee523a2206206994597C13D831ec7', // Bridged
  },

  // Primary routing venues on Monad
  venues: {
    // DEX routers with Monad support
    aerodrome: {
      router: '0x16AAB61dedBad9405299340D63Ee98D1bFd052d3',
      factory: '0x420DD381b31aEf6683db6B902084cB0FFECe40Da',
      stable: false, // Volatile pair routing
      name: 'Aerodrome',
      priority: 1, // Highest priority on Monad
      features: ['volatile', 'stable', 'concentrated'],
    },
    uniswapV3: {
      router: '0xE592427A0AEce92De3Edee1F18E0157C05861564',
      factory: '0x1F98431c8aD98523631AE4a59f267346ea3113cD',
      name: 'Uniswap V3',
      priority: 2,
      features: ['concentrated-liquidity', 'fee-tiers'],
    },
    curve: {
      router: '0x99a58482BD75cbab83b27EC03ca68fF489ee5f38',
      name: 'Curve',
      priority: 3,
      features: ['stable-swap', 'meta-pools'],
    },
    balancer: {
      vault: '0xBA12222222228d8Ba445958a75a0704d566BF2C8',
      name: 'Balancer',
      priority: 4,
      features: ['weighted-pools', 'stable-pools', 'liquidity-bootstrapping'],
    },
    // Aggregators
    zerox: {
      name: '0x',
      priority: 5,
      features: ['meta-aggregator'],
    },
    paraswap: {
      name: 'ParaSwap',
      priority: 6,
      features: ['meta-aggregator'],
    },
    oneInch: {
      name: '1Inch',
      priority: 7,
      features: ['meta-aggregator'],
    },
    cow: {
      name: 'CoW',
      priority: 8,
      features: ['intents', 'batch-auctions'],
    },
  },

  // Gas optimization settings
  gas: {
    // Monad has high throughput, lower gas costs
    maxPriorityFee: BigInt('1000000000'), // 1 gwei (very low)
    maxFeePerGas: BigInt('2000000000'),   // 2 gwei

    // Typical tx costs
    swapGasEstimate: {
      simple: 80000,      // Single hop
      multiHop: 150000,   // Multi-hop
      complex: 250000,    // Complex route
    },
  },

  // Performance settings
  performance: {
    // Monad's high TPS allows aggressive settings
    maxConcurrentQuotes: 50, // 50 parallel venue queries
    quoteTimeoutMs: 1500,    // Tight timeout for high throughput
    targetLatency: 800,      // Target sub-1 second

    // Caching strategy
    priceCache: {
      ttl: 3000,     // 3-second cache (frequent updates)
      maxSize: 1000, // Max cached pairs
    },
  },

  // Monad ecosystem integration
  ecosystem: {
    monadDAO: '0x0000000000000000000000000000000000000000',
    staking: '0x0000000000000000000000000000000000000000',
    governance: '0x0000000000000000000000000000000000000000',
  },

  // Settlement settings
  settlement: {
    // Standard ERC20 transfers
    confirmations: 1, // Monad finality is fast
    confirmationTimeMs: 2000, // ~2 seconds per block

    // Permit2 support (gas optimization)
    permit2: '0x000000000022D473030F116dDEE9F6B43aC78BA3',
  },

  // Rate limiting (Monad nodes are fast)
  rateLimit: {
    requestsPerSecond: 100,
    burstSize: 500,
    retryDelayMs: 100,
  },

  // Monitoring & alerts
  monitoring: {
    priceDeviationAlert: 0.5,  // Alert if price deviates >0.5% from average
    slippageWarn: 0.1,         // Warn if slippage >0.1%
    latencyWarn: 2000,         // Warn if quote takes >2s
  },
};

/**
 * Get RPC endpoint with fallback support
 */
export async function getMonadRPC(): Promise<string> {
  // Try primary first
  try {
    const response = await fetch(MONAD_CONFIG.rpc.primary, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        method: 'eth_chainId',
        params: [],
        id: 1,
      }),
    });

    if (response.ok) return MONAD_CONFIG.rpc.primary;
  } catch (err) {
    console.warn('Primary Monad RPC failed, trying fallback');
  }

  // Try fallbacks
  for (const fallback of MONAD_CONFIG.rpc.fallbacks) {
    try {
      const response = await fetch(fallback, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jsonrpc: '2.0',
          method: 'eth_chainId',
          params: [],
          id: 1,
        }),
      });

      if (response.ok) return fallback;
    } catch (err) {
      continue;
    }
  }

  // All failed, return primary anyway
  console.error('All Monad RPC endpoints failed, using primary as fallback');
  return MONAD_CONFIG.rpc.primary;
}

/**
 * Check if a venue is available on Monad
 */
export function isVenueAvailableOnMonad(venueName: string): boolean {
  return Object.values(MONAD_CONFIG.venues).some(v =>
    v.name.toLowerCase() === venueName.toLowerCase()
  );
}

/**
 * Get venue by priority for Monad
 */
export function getVenuesByPriority() {
  return Object.entries(MONAD_CONFIG.venues)
    .map(([key, config]) => ({
      ...config,
      id: key,
    }))
    .sort((a, b) => a.priority - b.priority);
}

/**
 * Get recommended venue for specific token pair on Monad
 */
export function recommendMonadVenue(tokenIn: string, tokenOut: string): string {
  // Aerodrome is default for MON pairs (highest priority)
  if (tokenIn === MONAD_CONFIG.tokens.MON ||
      tokenOut === MONAD_CONFIG.tokens.MON) {
    return 'aerodrome';
  }

  // Uniswap V3 for stables
  if ((tokenIn === MONAD_CONFIG.tokens.USDC && tokenOut === MONAD_CONFIG.tokens.USDT) ||
      (tokenIn === MONAD_CONFIG.tokens.USDT && tokenOut === MONAD_CONFIG.tokens.USDC)) {
    return 'curve'; // Curve is optimal for stables
  }

  // Default: use top-priority venue (Aerodrome)
  return 'aerodrome';
}

export default MONAD_CONFIG;
