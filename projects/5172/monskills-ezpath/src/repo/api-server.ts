/**
 * MONSKILLS EZ-Path API Server
 * Agent-facing HTTP API for multi-venue DEX routing
 *
 * Deploy to: Vercel, Railway, Cloud Run, or any Node.js host
 *
 * Environment variables:
 * - PORT: Server port (default: 3000)
 * - RATE_LIMIT_PER_MINUTE: Requests per minute (default: 120)
 * - LOG_LEVEL: debug | info | warn | error (default: info)
 */

import express, { Request, Response, NextFunction } from 'express';
import rateLimit from 'express-rate-limit';
import { getPrice, batchQuotes } from './index';

interface QuoteRequest {
  chain: 'base' | 'monad';
  sellToken: string;
  buyToken: string;
  sellAmount: string;
  slippageTolerance?: number;
}

interface ApiError {
  error: string;
  message: string;
  details?: Record<string, any>;
  timestamp: string;
}

// Initialize Express app
const app = express();

// Middleware
app.use(express.json({ limit: '10mb' }));

// Request logging
app.use((req: Request, res: Response, next: NextFunction) => {
  const start = Date.now();
  res.on('finish', () => {
    const duration = Date.now() - start;
    console.log(
      `[${new Date().toISOString()}] ${req.method} ${req.path} ${res.statusCode} ${duration}ms`
    );
  });
  next();
});

// Health check endpoint (no rate limit)
app.get('/v1/health', (req: Request, res: Response) => {
  res.json({
    status: 'healthy',
    uptime_ms: process.uptime() * 1000,
    venues: {
      healthy: [
        '0x',
        'Aerodrome',
        'Uniswap V3',
        'Curve',
        'Balancer',
        'Uniswap V2',
        'ParaSwap',
        '1Inch',
        'CoW',
        'Synthetix',
      ],
      degraded: [],
    },
    timestamp: new Date().toISOString(),
  });
});

// Chains endpoint (no rate limit)
app.get('/v1/chains', (req: Request, res: Response) => {
  res.json({
    chains: [
      {
        id: 'base',
        name: 'Base',
        chain_id: 8453,
        status: 'production',
        venues_count: 10,
        settlement_support: true,
      },
      {
        id: 'monad',
        name: 'Monad Testnet',
        chain_id: 10143,
        status: 'testnet',
        venues_count: 10,
        settlement_support: true,
      },
    ],
  });
});

// Venues endpoint (no rate limit)
app.get('/v1/venues', (req: Request, res: Response) => {
  res.json({
    venues: [
      { id: '0x', name: '0x', status: 'operational', chains: ['base', 'monad'] },
      {
        id: 'aerodrome',
        name: 'Aerodrome',
        status: 'operational',
        chains: ['base', 'monad'],
      },
      {
        id: 'uniswap-v3',
        name: 'Uniswap V3',
        status: 'operational',
        chains: ['base', 'monad'],
      },
      { id: 'curve', name: 'Curve', status: 'operational', chains: ['base', 'monad'] },
      {
        id: 'balancer',
        name: 'Balancer',
        status: 'operational',
        chains: ['base', 'monad'],
      },
      {
        id: 'uniswap-v2',
        name: 'Uniswap V2',
        status: 'operational',
        chains: ['base', 'monad'],
      },
      {
        id: 'paraswap',
        name: 'ParaSwap',
        status: 'operational',
        chains: ['base', 'monad'],
      },
      { id: '1inch', name: '1Inch', status: 'operational', chains: ['base', 'monad'] },
      { id: 'cow', name: 'CoW', status: 'operational', channels: ['base', 'monad'] },
      {
        id: 'synthetix',
        name: 'Synthetix',
        status: 'operational',
        chains: ['base', 'monad'],
      },
    ],
  });
});

// Rate limiter (applied to quote endpoints)
const quoteLimiter = rateLimit({
  windowMs: 1 * 60 * 1000, // 1 minute
  max: parseInt(process.env.RATE_LIMIT_PER_MINUTE || '120'),
  message: 'Too many requests, please try again later.',
  standardHeaders: true, // Return rate limit info in `RateLimit-*` headers
  skip: (req: Request) => {
    // Don't rate limit health checks
    return req.path === '/v1/health';
  },
  keyGenerator: (req: Request) => {
    // Rate limit by IP address
    return req.ip || 'unknown';
  },
});

// Apply rate limiter
app.use(quoteLimiter);

// Quote endpoint
app.post('/v1/quote', async (req: Request, res: Response) => {
  const startTime = Date.now();

  try {
    const { chain, sellToken, buyToken, sellAmount, slippageTolerance } = req.body;

    // Validation
    if (!chain || !sellToken || !buyToken || !sellAmount) {
      const missingFields = [];
      if (!chain) missingFields.push('chain');
      if (!sellToken) missingFields.push('sellToken');
      if (!buyToken) missingFields.push('buyToken');
      if (!sellAmount) missingFields.push('sellAmount');

      return res.status(400).json({
        error: 'INVALID_REQUEST',
        message: `Missing required fields: ${missingFields.join(', ')}`,
        details: { missing_fields: missingFields },
        timestamp: new Date().toISOString(),
      } as ApiError);
    }

    // Validate chain
    if (!['base', 'monad'].includes(chain)) {
      return res.status(400).json({
        error: 'INVALID_REQUEST',
        message: `Invalid chain '${chain}'. Must be 'base' or 'monad'`,
        details: { invalid_field: 'chain', valid_options: ['base', 'monad'] },
        timestamp: new Date().toISOString(),
      } as ApiError);
    }

    // Validate addresses
    const addressRegex = /^0x[a-fA-F0-9]{40}$/;
    if (!addressRegex.test(sellToken)) {
      return res.status(400).json({
        error: 'INVALID_REQUEST',
        message: 'Invalid sellToken address format',
        details: { invalid_field: 'sellToken' },
        timestamp: new Date().toISOString(),
      } as ApiError);
    }

    if (!addressRegex.test(buyToken)) {
      return res.status(400).json({
        error: 'INVALID_REQUEST',
        message: 'Invalid buyToken address format',
        details: { invalid_field: 'buyToken' },
        timestamp: new Date().toISOString(),
      } as ApiError);
    }

    // Validate amount
    if (!/^[0-9]+$/.test(sellAmount.toString())) {
      return res.status(400).json({
        error: 'INVALID_REQUEST',
        message: 'sellAmount must be a numeric string (wei)',
        details: { invalid_field: 'sellAmount' },
        timestamp: new Date().toISOString(),
      } as ApiError);
    }

    // Get quote
    const result = await getPrice(chain, sellToken, buyToken, sellAmount.toString());

    if (!result || !('price' in result)) {
      return res.status(400).json({
        error: 'INSUFFICIENT_LIQUIDITY',
        message: 'No liquidity available for this pair on any venue',
        details: {
          pair: `${sellToken.slice(0, 6)}.../${buyToken.slice(0, 6)}...`,
          chain,
          venues_checked: 10,
        },
        timestamp: new Date().toISOString(),
      } as ApiError);
    }

    const latencyMs = Date.now() - startTime;

    // Format response
    return res.status(200).json({
      quote_id: `q_${chain}_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
      chain_id: chain,
      sell_token: sellToken,
      buy_token: buyToken,
      sell_amount: sellAmount.toString(),
      buy_amount: result.price,
      route: {
        venues: result.sources,
        proportions: result.sources.map(() => 1.0 / result.sources.length), // Simplified
      },
      gas_estimate: '150000', // Placeholder
      execution_price: (BigInt(result.price) / BigInt(sellAmount)).toString(),
      expires_at: Math.floor(Date.now() / 1000) + 300, // 5 minutes
      latency_ms: latencyMs,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error('[ERROR]', error);

    const latencyMs = Date.now() - startTime;

    // Check for timeout
    if ((error as any).code === 'ECONNABORTED' || latencyMs > 2000) {
      return res.status(408).json({
        error: 'QUOTE_TIMEOUT',
        message: 'Quote request timed out',
        details: { timeout_ms: latencyMs },
        timestamp: new Date().toISOString(),
      } as ApiError);
    }

    // Server error
    return res.status(500).json({
      error: 'UPSTREAM_ERROR',
      message: 'Internal server error',
      details: { error_message: (error as Error).message },
      timestamp: new Date().toISOString(),
    } as ApiError);
  }
});

// Batch quotes endpoint
app.post('/v1/quote/batch', async (req: Request, res: Response) => {
  const startTime = Date.now();

  try {
    const { requests } = req.body;

    // Validation
    if (!Array.isArray(requests) || requests.length === 0) {
      return res.status(400).json({
        error: 'INVALID_REQUEST',
        message: 'requests must be a non-empty array',
        details: {},
        timestamp: new Date().toISOString(),
      } as ApiError);
    }

    if (requests.length > 10) {
      return res.status(400).json({
        error: 'INVALID_REQUEST',
        message: 'Maximum 10 requests per batch',
        details: { max_requests: 10, provided: requests.length },
        timestamp: new Date().toISOString(),
      } as ApiError);
    }

    // Execute batch
    const results = await batchQuotes(requests);

    const latencyMs = Date.now() - startTime;

    return res.status(200).json({
      batch_id: `b_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
      results: results.map((result, i) => ({
        quote_id: `q_batch_${i}`,
        chain_id: requests[i].chain,
        sell_token: requests[i].sellToken,
        buy_token: requests[i].buyToken,
        sell_amount: requests[i].sellAmount,
        buy_amount: 'price' in result ? result.price : '0',
        route: {
          venues: 'sources' in result ? result.sources : [],
          proportions: ('sources' in result)
            ? result.sources.map(() => 1.0 / result.sources.length)
            : [],
        },
        expires_at: Math.floor(Date.now() / 1000) + 300,
        latency_ms: latencyMs,
        timestamp: new Date().toISOString(),
      })),
      latency_ms: latencyMs,
    });
  } catch (error) {
    console.error('[ERROR]', error);

    return res.status(500).json({
      error: 'UPSTREAM_ERROR',
      message: 'Batch processing failed',
      details: { error_message: (error as Error).message },
      timestamp: new Date().toISOString(),
    } as ApiError);
  }
});

// 404 handler
app.use((req: Request, res: Response) => {
  res.status(404).json({
    error: 'NOT_FOUND',
    message: `Endpoint not found: ${req.method} ${req.path}`,
    timestamp: new Date().toISOString(),
  } as ApiError);
});

// Error handler
app.use((err: any, req: Request, res: Response, next: NextFunction) => {
  console.error('[ERROR]', err);

  res.status(500).json({
    error: 'SERVER_ERROR',
    message: 'Internal server error',
    details: { error_message: err.message },
    timestamp: new Date().toISOString(),
  } as ApiError);
});

// Start server
const PORT = parseInt(process.env.PORT || '3000');
app.listen(PORT, () => {
  console.log(`\n╔════════════════════════════════════════╗`);
  console.log(`║  MONSKILLS EZ-Path API Server v0.1.1  ║`);
  console.log(`╚════════════════════════════════════════╝\n`);
  console.log(`🚀 Server running on http://localhost:${PORT}`);
  console.log(`📍 Endpoints:`);
  console.log(`   POST   /v1/quote              Get DEX quote`);
  console.log(`   POST   /v1/quote/batch        Batch quotes`);
  console.log(`   GET    /v1/health             Health check`);
  console.log(`   GET    /v1/chains             Supported chains`);
  console.log(`   GET    /v1/venues             Supported venues`);
  console.log(`\n📚 Docs: https://github.com/infiniteezverse/monskills-ezpath`);
  console.log(`💬 Issues: https://github.com/infiniteezverse/monskills-ezpath/issues\n`);
});

export default app;
