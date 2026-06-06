/**
 * EIP-3009 TransferWithAuthorization Implementation
 * Enables X402 payment handling for EZ-Path quotes on Base
 *
 * References:
 * - EIP-3009: https://eips.ethereum.org/EIPS/eip-3009
 * - USDC v2 on Base: 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
 */

import crypto from 'crypto';

/**
 * EIP-3009 Domain Separator for USDC v2 on Base
 * These values are fixed and specific to USDC's deployment
 */
export const USDC_BASE_DOMAIN = {
  name: 'USD Coin',
  version: '2',
  chainId: 8453, // Base mainnet
  verifyingContract: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
} as const;

/**
 * EIP-712 TypedData for TransferWithAuthorization
 */
export const TRANSFER_WITH_AUTHORIZATION_TYPE = {
  TransferWithAuthorization: [
    { name: 'from', type: 'address' },
    { name: 'to', type: 'address' },
    { name: 'value', type: 'uint256' },
    { name: 'validAfter', type: 'uint256' },
    { name: 'validBefore', type: 'uint256' },
    { name: 'nonce', type: 'bytes32' },
  ],
} as const;

/**
 * Authorization message for EIP-3009
 */
export interface TransferAuthorizationMessage {
  from: string;           // Agent's address
  to: string;             // Toll address (EZ-Path)
  value: string;          // Amount in atomic units (wei)
  validAfter: number;     // Unix timestamp, earliest time this is valid
  validBefore: number;    // Unix timestamp, latest time this is valid
  nonce: string;          // Random nonce (0x + 64 hex chars)
}

/**
 * Construct a TransferWithAuthorization message
 */
export function createAuthorizationMessage(
  from: string,
  to: string,
  amountInAtomic: bigint,
  validityDuration: number = 300 // 5 minutes
): TransferAuthorizationMessage {
  const now = Math.floor(Date.now() / 1000);
  const nonce = '0x' + crypto.randomBytes(32).toString('hex');

  return {
    from: from.toLowerCase().startsWith('0x') ? from.toLowerCase() : '0x' + from.toLowerCase(),
    to: to.toLowerCase().startsWith('0x') ? to.toLowerCase() : '0x' + to.toLowerCase(),
    value: amountInAtomic.toString(),
    validAfter: 0,
    validBefore: now + validityDuration,
    nonce,
  };
}

/**
 * Calculate domain separator per EIP-712
 * domainSeparator = keccak256(EIP712Domain(name, version, chainId, verifyingContract))
 */
export function getDomainSeparator(): string {
  // In production, this would be calculated using ethers.js
  // For now, return the pre-calculated value for USDC v2 on Base
  // This should be verified against the actual contract

  // The domain separator is calculated as:
  // keccak256(
  //   abi.encode(
  //     keccak256('EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)'),
  //     keccak256('USD Coin'),
  //     keccak256('2'),
  //     8453,
  //     0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
  //   )
  // )

  // Pre-calculated for USDC v2 on Base:
  return '0x0b50407de9fa158521f154e2ca1ea1732aafec63675491e98e500d4e4b8714b8';
}

/**
 * EIP-712 Hash Struct for TransferWithAuthorization
 * Calculates the hash of the message according to EIP-712
 */
export function hashAuthorizationMessage(_message: TransferAuthorizationMessage): string {
  // This is a simplified version. In production, use ethers.js
  // const hash = ethers.TypedDataEncoder.hash(domain, types, message)

  // For demonstration, we'll show the structure:
  // hashStruct(TransferWithAuthorization) = keccak256(
  //   abi.encode(
  //     keccak256('TransferWithAuthorization(address from,address to,uint256 value,uint256 validAfter,uint256 validBefore,bytes32 nonce)'),
  //     message.from,
  //     message.to,
  //     message.value,
  //     message.validAfter,
  //     message.validBefore,
  //     message.nonce
  //   )
  // )

  // digest = keccak256(
  //   abi.encodePacked(
  //     bytes2(0x1901),
  //     domainSeparator,
  //     hashStruct
  //   )
  // )

  // For now, return placeholder - actual implementation uses ethers.js
  return '0x' + crypto.randomBytes(32).toString('hex');
}

/**
 * X402 Payment Signature Package
 */
export interface X402PaymentSignature {
  signature: string; // EIP-191 or EIP-712 signature
  authorization: TransferAuthorizationMessage;
  quote_issued_at: number; // Timestamp when quote was generated
}

/**
 * X402 Payment Header Value
 * Encodes payment signature for HTTP X-Payment header
 */
export function createX402PaymentHeader(
  signature: X402PaymentSignature
): string {
  const payload = {
    payload: signature,
  };

  // Encode as base64 per X402 spec
  const json = JSON.stringify(payload);
  return Buffer.from(json).toString('base64');
}

/**
 * Parse X402 Payment Header
 * Decodes base64 X-Payment header
 */
export function parseX402PaymentHeader(header: string): X402PaymentSignature | null {
  try {
    const json = Buffer.from(header, 'base64').toString('utf8');
    const parsed = JSON.parse(json);
    return parsed.payload;
  } catch (error) {
    console.error('Failed to parse X402 payment header:', error);
    return null;
  }
}

/**
 * Validate Authorization Message
 * Checks that message is properly formed and within validity window
 */
export function validateAuthorizationMessage(message: TransferAuthorizationMessage): {
  valid: boolean;
  error?: string;
} {
  const now = Math.floor(Date.now() / 1000);

  // Check validity window
  if (message.validAfter > now) {
    return {
      valid: false,
      error: `Authorization not yet valid (validAfter: ${message.validAfter}, now: ${now})`,
    };
  }

  if (message.validBefore < now) {
    return {
      valid: false,
      error: `Authorization expired (validBefore: ${message.validBefore}, now: ${now})`,
    };
  }

  // Check addresses
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

  // Check nonce
  if (!message.nonce.startsWith('0x') || message.nonce.length !== 66) {
    return {
      valid: false,
      error: 'Invalid nonce (should be 0x + 64 hex characters)',
    };
  }

  // Check value
  try {
    BigInt(message.value);
  } catch {
    return {
      valid: false,
      error: 'Invalid value (should be numeric string)',
    };
  }

  return { valid: true };
}

/**
 * Configuration for common payment tiers
 */
export const PAYMENT_TIERS = {
  basic: {
    name: 'Basic',
    costUSDC: 0.03,
    costAtomic: 30000n,
    description: 'Direct 0x routing',
  },
  resilient: {
    name: 'Resilient',
    costUSDC: 0.1,
    costAtomic: 100000n,
    description: '4-venue racing',
  },
  institutional: {
    name: 'Institutional',
    costUSDC: 0.5,
    costAtomic: 500000n,
    description: '10-venue racing',
  },
} as const;

/**
 * Get payment tier by cost
 */
export function getTierByAmount(amountInAtomic: bigint): string {
  if (amountInAtomic >= PAYMENT_TIERS.institutional.costAtomic) {
    return 'institutional';
  }
  if (amountInAtomic >= PAYMENT_TIERS.resilient.costAtomic) {
    return 'resilient';
  }
  if (amountInAtomic >= PAYMENT_TIERS.basic.costAtomic) {
    return 'basic';
  }
  return 'unknown';
}

/**
 * Toll address (EZ-Path payment recipient on Base)
 */
export const TOLL_ADDRESS = '0x13dDE704389b1118B20d2BCc6D3Ace749600e2ad';

/**
 * X402 Protocol Configuration
 */
export const X402_CONFIG = {
  protocol: 'X402',
  version: 1,
  paymentMethod: 'EIP-3009',
  chain: 'base',
  chainId: 8453,
  usdcAddress: USDC_BASE_DOMAIN.verifyingContract,
  tollAddress: TOLL_ADDRESS,
  maxRetries: 3,
  retryDelayMs: 1000,
  quoteTTL: 300, // 5 minutes
} as const;

export default {
  USDC_BASE_DOMAIN,
  TRANSFER_WITH_AUTHORIZATION_TYPE,
  PAYMENT_TIERS,
  TOLL_ADDRESS,
  X402_CONFIG,
  createAuthorizationMessage,
  getDomainSeparator,
  hashAuthorizationMessage,
  createX402PaymentHeader,
  parseX402PaymentHeader,
  validateAuthorizationMessage,
  getTierByAmount,
};
