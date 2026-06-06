/**
 * EZ-Path MONSKILLS Plugin
 * Exposes EZ-Path DEX routing as a MONSKILLS skill for agent use
 */

import axios from 'axios';
import { EZPathQuoteRequest, EZPathResponse, QuoteResult } from './types/ezpath';

const EZPATH_URL = process.env.EZPATH_URL || 'https://ezpath.myezverse.xyz';
const API_ENDPOINT = `${EZPATH_URL}/api/v1/quote`;

/**
 * Get a DEX price quote from EZ-Path
 * Races 10 venues and returns the best price
 *
 * @param request - Quote parameters (chain, tokens, amount)
 * @returns Quote result with price and sources
 */
export async function getQuote(request: EZPathQuoteRequest): Promise<QuoteResult> {
  try {
    // Validate inputs
    if (!request.sellToken || !request.buyToken || !request.sellAmount) {
      return {
        success: false,
        error: 'Missing required parameters: sellToken, buyToken, sellAmount',
      };
    }

    // Build query parameters
    const params = new URLSearchParams({
      chain: request.chain || 'base',
      sellToken: request.sellToken,
      buyToken: request.buyToken,
      sellAmount: request.sellAmount,
    });

    if (request.slippagePercentage !== undefined) {
      params.append('slippagePercentage', request.slippagePercentage.toString());
    }

    // Call EZ-Path endpoint
    const response = await axios.get<EZPathResponse>(`${API_ENDPOINT}?${params}`, {
      timeout: 10000,
      validateStatus: () => true, // Accept all statuses
    });

    // Handle 402 Payment Required
    if (response.status === 402) {
      const data = response.data as any;
      return {
        success: false,
        paymentRequired: true,
        estimatedFee: {
          usd: data.unlock_fee_usd,
          atomic: data.tiers?.basic?.min_atomic || '30000',
          token: 'USDC',
        },
        error: `Payment required: ${data.unlock_fee_usd} USDC via X402 EIP-3009`,
      };
    }

    // Handle successful quote
    if (response.status === 200) {
      const data = response.data as any;
      return {
        success: true,
        data: {
          status: 'ok',
          request_id: data.request_id,
          sellToken: data.sellToken,
          buyToken: data.buyToken,
          sellAmount: data.sellAmount,
          buyAmount: data.buyAmount,
          price: data.price,
          sources: data.sources || [],
          routingEngine: data.routingEngine || 'unknown',
          tier: data.tier || 'basic',
          settlement_tx: data.settlement_tx,
        },
      };
    }

    // Handle errors
    return {
      success: false,
      error: `EZ-Path error (${response.status}): ${JSON.stringify(response.data)}`,
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return {
      success: false,
      error: `Request failed: ${message}`,
    };
  }
}

/**
 * Get price for a token pair in human-readable format
 * Convenience wrapper around getQuote
 *
 * @param chain - Blockchain (base, monad, etc.)
 * @param sellToken - Token to sell (address)
 * @param buyToken - Token to buy (address)
 * @param amount - Amount in atomic units
 * @returns Price as decimal string
 */
export async function getPrice(
  chain: string,
  sellToken: string,
  buyToken: string,
  amount: string,
): Promise<{ price: string; sources: string[] } | { error: string }> {
  const result = await getQuote({ chain: chain as any, sellToken, buyToken, sellAmount: amount });

  if (result.success && result.data) {
    return {
      price: result.data.price,
      sources: result.data.sources.map((s) => s.name),
    };
  }

  return {
    error: result.error || 'Failed to get price',
  };
}

/**
 * Batch quote multiple pairs
 * Useful for portfolio valuation
 */
export async function batchQuotes(
  requests: EZPathQuoteRequest[],
): Promise<QuoteResult[]> {
  return Promise.all(requests.map((req) => getQuote(req)));
}

// Export types
export * from './types/ezpath';

// MONSKILLS-compatible exports
export const skill = {
  name: 'ez-path',
  version: '0.1.0',
  description: 'DEX price quotes via EZ-Path (races 10 venues)',
  handlers: {
    getQuote,
    getPrice,
    batchQuotes,
  },
};

export default skill;
