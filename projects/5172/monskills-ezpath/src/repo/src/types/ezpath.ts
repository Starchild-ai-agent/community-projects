/**
 * EZ-Path Quote Types
 * Matches the EZ-Path API response schema
 */

export interface EZPathQuoteRequest {
  chain: 'base' | 'monad' | 'arbitrum' | 'optimism' | 'polygon';
  sellToken: string; // ERC-20 token address
  buyToken: string; // ERC-20 token address
  sellAmount: string; // Amount in atomic units (base decimals)
  slippagePercentage?: number; // Optional slippage tolerance (e.g., 0.01 for 1%)
}

export interface EZPathSource {
  name: string; // Venue name (e.g., "0x", "Aerodrome", "Uniswap V3")
  buyAmount: string; // Output amount from this venue
  gasEstimate?: string; // Estimated gas (if available)
}

export interface EZPathQuoteResponse {
  status: 'ok' | 'payment_required' | 'bad_request' | 'internal_error';
  request_id: string;
  sellToken: string;
  buyToken: string;
  sellAmount: string;
  buyAmount: string;
  price: string; // Human-readable price (e.g., "0.000503")
  sources: EZPathSource[];
  routingEngine: string; // Winning venue
  tier: 'basic' | 'resilient' | 'institutional';
  settlement_tx?: string; // Transaction hash (if settled on-chain)
}

export interface EZPathPaymentRequired {
  status: 'payment_required';
  x402Version: number;
  accepts: Array<{
    scheme: string;
    network: string;
    maxAmountRequired: string;
    resource: string;
    description: string;
    mimeType: string;
    payTo: string;
    maxTimeoutSeconds: number;
    asset: string;
    extra: Record<string, any>;
  }>;
  unlock_fee_usd: number;
  request_id: string;
  tiers: Record<string, {
    min_atomic: string;
    min_usdc: number;
    description: string;
  }>;
}

export type EZPathResponse = EZPathQuoteResponse | EZPathPaymentRequired;

export interface QuoteResult {
  success: boolean;
  data?: EZPathQuoteResponse;
  error?: string;
  paymentRequired?: boolean;
  estimatedFee?: {
    usd: number;
    atomic: string;
    token: 'USDC';
  };
}
