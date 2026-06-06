/**
 * Quote Execution with X402 Payment
 * Handles the complete flow: probe → payment signing → retry → settlement
 *
 * Flow:
 * 1. GET /api/v1/quote → HTTP 402 Payment Required
 * 2. Extract toll address and payment amount from 402 response
 * 3. Create EIP-3009 TransferWithAuthorization message
 * 4. Sign message with agent's private key
 * 5. Retry GET /api/v1/quote with X-Payment header
 * 6. Return settlement transaction and quote data
 */

import axios from 'axios';
import {
  createAuthorizationMessage,
  createX402PaymentHeader,
  getTierByAmount,
  TOLL_ADDRESS,
} from './eip3009';
import type { TransferAuthorizationMessage, X402PaymentSignature } from './eip3009';
import type { EZPathQuoteRequest } from '../types/ezpath';

/**
 * Quote execution result
 */
export interface ExecutionResult {
  success: boolean;
  data?: {
    status: string;
    request_id: string;
    sellToken: string;
    buyToken: string;
    sellAmount: string;
    buyAmount: string;
    price: string;
    sources: Array<{ name: string; buyAmount: string }>;
    routingEngine: string;
    tier: string;
    settlement_tx?: string;
  };
  error?: string;
  paymentRequired?: boolean;
  estimatedFee?: {
    usd: number;
    atomic: string;
    token: 'USDC';
  };
  paymentSignature?: X402PaymentSignature;
  retries: number;
}

/**
 * Quote Executor
 * Handles quotes with optional X402 payment
 */
export class QuoteExecutor {
  private ezPathUrl: string;
  private signingFunction?: (message: TransferAuthorizationMessage) => Promise<string>;
  private agentAddress?: string;
  private maxRetries: number = 3;
  private retryDelayMs: number = 1000;

  constructor(
    ezPathUrl: string = 'https://ezpath.myezverse.xyz',
    options?: {
      maxRetries?: number;
      retryDelayMs?: number;
      signingFunction?: (message: TransferAuthorizationMessage) => Promise<string>;
      agentAddress?: string;
    }
  ) {
    this.ezPathUrl = ezPathUrl;
    if (options?.maxRetries) this.maxRetries = options.maxRetries;
    if (options?.retryDelayMs) this.retryDelayMs = options.retryDelayMs;
    if (options?.signingFunction) this.signingFunction = options.signingFunction;
    if (options?.agentAddress) this.agentAddress = options.agentAddress;
  }

  /**
   * Execute quote with optional X402 payment
   */
  async executeQuote(
    request: EZPathQuoteRequest,
    paymentSigningFunction?: (message: TransferAuthorizationMessage) => Promise<string>
  ): Promise<ExecutionResult> {
    let retries = 0;
    const maxRetries = this.maxRetries;
    const agentAddress = this.agentAddress || '0x0000000000000000000000000000000000000000';

    try {
      // Step 1: Initial probe (no payment)
      console.log('[EZ-Path] Probing endpoint...');

      const probeResponse = await this.makeQuoteRequest(request);

      // Check for 402 Payment Required
      if (probeResponse.status === 402) {
        const paymentRequired = probeResponse.data as any;
        console.log('[EZ-Path] Payment required (HTTP 402)');

        // Extract payment information
        const feeUSD = paymentRequired.unlock_fee_usd || 0.03;
        const feeAtomic = getTierBasedAmount(feeUSD);
        const tier = getTierByAmount(feeAtomic);

        console.log(`[X402] Tier: ${tier}, Fee: $${feeUSD} USDC (${feeAtomic.toString()} atomic)`);

        // Step 2: Create authorization message
        const authMessage = createAuthorizationMessage(
          agentAddress,
          TOLL_ADDRESS,
          feeAtomic,
          300 // 5 minute validity
        );

        console.log(`[X402] Authorization created`);
        console.log(`   Valid: ${new Date(authMessage.validAfter * 1000).toISOString()}`);
        console.log(`   Expires: ${new Date(authMessage.validBefore * 1000).toISOString()}`);
        console.log(`   Nonce: ${authMessage.nonce}`);

        // Validate message before signing
        const validation = validateAuthorizationMessage(authMessage);
        if (!validation.valid) {
          return {
            success: false,
            error: `Invalid authorization message: ${validation.error}`,
            paymentRequired: true,
            estimatedFee: {
              usd: feeUSD,
              atomic: feeAtomic.toString(),
              token: 'USDC',
            },
            retries,
          };
        }

        // Step 3: Sign the message
        let signature: string;
        const signingFn = paymentSigningFunction || this.signingFunction;

        if (!signingFn) {
          return {
            success: false,
            error: 'No signing function provided. Cannot sign X402 payment.',
            paymentRequired: true,
            estimatedFee: {
              usd: feeUSD,
              atomic: feeAtomic.toString(),
              token: 'USDC',
            },
            retries,
          };
        }

        try {
          console.log('[X402] Signing authorization...');
          signature = await signingFn(authMessage);
          console.log(`[X402] Signature: ${signature.substring(0, 20)}...`);
        } catch (signError) {
          return {
            success: false,
            error: `Failed to sign X402 payment: ${String(signError)}`,
            paymentRequired: true,
            estimatedFee: {
              usd: feeUSD,
              atomic: feeAtomic.toString(),
              token: 'USDC',
            },
            retries,
          };
        }

        // Step 4: Create X402 payment header
        const paymentSignature: X402PaymentSignature = {
          signature,
          authorization: authMessage,
          quote_issued_at: Math.floor(Date.now() / 1000),
        };

        const xPaymentHeader = createX402PaymentHeader(paymentSignature);

        // Step 5: Retry with payment header
        console.log('[X402] Retrying quote with payment...');

        let paidResponse = await this.makeQuoteRequest(request, xPaymentHeader);
        retries++;

        // Retry logic for transient failures
        while (paidResponse.status !== 200 && retries < maxRetries) {
          console.log(
            `[X402] Attempt ${retries}: Got ${paidResponse.status}, retrying in ${this.retryDelayMs}ms...`
          );
          await this.delay(this.retryDelayMs);

          paidResponse = await this.makeQuoteRequest(request, xPaymentHeader);
          retries++;
        }

        // Check final response
        if (paidResponse.status === 200) {
          const data = paidResponse.data as any;
          console.log(`[EZ-Path] ✅ Quote successful`);
          console.log(`   Buy amount: ${data.buyAmount}`);
          console.log(`   Best engine: ${data.routingEngine}`);
          console.log(`   Settlement TX: ${data.settlement_tx || 'pending'}`);

          return {
            success: true,
            data: {
              status: data.status,
              request_id: data.request_id,
              sellToken: data.sellToken,
              buyToken: data.buyToken,
              sellAmount: data.sellAmount,
              buyAmount: data.buyAmount,
              price: data.price,
              sources: data.sources || [],
              routingEngine: data.routingEngine || 'unknown',
              tier: tier,
              settlement_tx: data.settlement_tx,
            },
            paymentSignature,
            retries,
          };
        } else {
          return {
            success: false,
            error: `Quote failed after ${retries} attempts: ${paidResponse.status}`,
            retries,
          };
        }
      } else if (probeResponse.status === 200) {
        // No payment required, return quote directly
        const data = probeResponse.data as any;
        console.log('[EZ-Path] ✅ Quote successful (no payment required)');

        return {
          success: true,
          data: {
            status: data.status,
            request_id: data.request_id,
            sellToken: data.sellToken,
            buyToken: data.buyToken,
            sellAmount: data.sellAmount,
            buyAmount: data.buyAmount,
            price: data.price,
            sources: data.sources || [],
            routingEngine: data.routingEngine || 'unknown',
            tier: 'basic',
          },
          retries,
        };
      } else {
        return {
          success: false,
          error: `Unexpected status: ${probeResponse.status}`,
          retries,
        };
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error(`[EZ-Path] Error: ${message}`);

      return {
        success: false,
        error: `Request failed: ${message}`,
        retries,
      };
    }
  }

  /**
   * Make quote request (internal)
   */
  private async makeQuoteRequest(request: EZPathQuoteRequest, xPaymentHeader?: string) {
    const params = new URLSearchParams({
      chain: request.chain || 'base',
      sellToken: request.sellToken,
      buyToken: request.buyToken,
      sellAmount: request.sellAmount,
    });

    if (request.slippagePercentage !== undefined) {
      params.append('slippagePercentage', request.slippagePercentage.toString());
    }

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (xPaymentHeader) {
      headers['X-Payment'] = xPaymentHeader;
    }

    try {
      const response = await axios.get(`${this.ezPathUrl}/api/v1/quote?${params}`, {
        headers,
        timeout: 10000,
        validateStatus: () => true, // Accept all statuses
      });

      return response;
    } catch (error) {
      throw error;
    }
  }

  /**
   * Delay utility
   */
  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

/**
 * Get tier-based payment amount
 */
function getTierBasedAmount(feeUSD: number): bigint {
  // Map USD fee to atomic USDC (6 decimals)
  const atomic = Math.round(feeUSD * 1e6);
  return BigInt(atomic);
}

/**
 * Validate authorization message
 */
function validateAuthorizationMessage(message: TransferAuthorizationMessage): {
  valid: boolean;
  error?: string;
} {
  const now = Math.floor(Date.now() / 1000);

  if (message.validBefore < now) {
    return {
      valid: false,
      error: 'Authorization expired',
    };
  }

  if (!message.from.startsWith('0x') || message.from.length !== 42) {
    return {
      valid: false,
      error: 'Invalid from address',
    };
  }

  if (!message.to.startsWith('0x') || message.to.length !== 42) {
    return {
      valid: false,
      error: 'Invalid to address',
    };
  }

  if (!message.nonce.startsWith('0x') || message.nonce.length !== 66) {
    return {
      valid: false,
      error: 'Invalid nonce',
    };
  }

  return { valid: true };
}

export default QuoteExecutor;
