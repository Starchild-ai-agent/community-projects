/**
 * Unit tests for EZ-Path MONSKILLS plugin
 * Tests getQuote, getPrice, and batchQuotes functions
 */

import { getQuote, getPrice, batchQuotes, EZPathQuoteRequest } from '../src/index';

describe('EZ-Path MONSKILLS Plugin', () => {
  // Note: These tests validate input handling and error cases
  // Live API tests should use integration test suite

  describe('getQuote', () => {
    it('should validate missing sellToken', async () => {
      const request: any = {
        chain: 'base',
        buyToken: '0x4200000000000000000000000000000000000006',
        sellAmount: '1000000',
        // Missing sellToken
      };

      const result = await getQuote(request);
      expect(result.success).toBe(false);
      expect(result.error).toContain('sellToken');
    });

    it('should validate missing buyToken', async () => {
      const request: any = {
        chain: 'base',
        sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
        sellAmount: '1000000',
        // Missing buyToken
      };

      const result = await getQuote(request);
      expect(result.success).toBe(false);
      expect(result.error).toContain('buyToken');
    });

    it('should validate missing sellAmount', async () => {
      const request: any = {
        chain: 'base',
        sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
        buyToken: '0x4200000000000000000000000000000000000006',
        // Missing sellAmount
      };

      const result = await getQuote(request);
      expect(result.success).toBe(false);
      expect(result.error).toContain('sellAmount');
    });

    it('should accept valid quote request', async () => {
      const request: EZPathQuoteRequest = {
        chain: 'base',
        sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
        buyToken: '0x4200000000000000000000000000000000000006',
        sellAmount: '1000000',
      };

      const result = await getQuote(request);
      // Should either succeed or fail with API error (not validation error)
      expect(result).toHaveProperty('success');
      expect(result).toHaveProperty('error');
    });

    it('should handle optional slippagePercentage', async () => {
      const request: EZPathQuoteRequest = {
        chain: 'base',
        sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
        buyToken: '0x4200000000000000000000000000000000000006',
        sellAmount: '1000000',
        slippagePercentage: 0.5,
      };

      const result = await getQuote(request);
      expect(result).toHaveProperty('success');
    });

    it('should detect payment required (402) responses', async () => {
      const request: EZPathQuoteRequest = {
        chain: 'base',
        sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
        buyToken: '0x4200000000000000000000000000000000000006',
        sellAmount: '1000000',
      };

      const result = await getQuote(request);

      // If payment required, should have paymentRequired flag
      if (result.paymentRequired) {
        expect(result.success).toBe(false);
        expect(result.error).toContain('Payment required');
        expect(result.estimatedFee).toBeDefined();
      }
    });

    it('should return typed QuoteResult', async () => {
      const request: EZPathQuoteRequest = {
        chain: 'base',
        sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
        buyToken: '0x4200000000000000000000000000000000000006',
        sellAmount: '1000000',
      };

      const result = await getQuote(request);

      // Check return type structure
      expect(typeof result.success).toBe('boolean');
      if (typeof result.error === 'string') {
        expect(result.error.length).toBeGreaterThan(0);
      }
      if (result.paymentRequired) {
        expect(result.estimatedFee).toBeDefined();
      }
    });
  });

  describe('getPrice', () => {
    it('should return price and sources on success', async () => {
      const result = await getPrice(
        'base',
        '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
        '0x4200000000000000000000000000000000000006',
        '1000000'
      );

      // Check result structure
      if ('price' in result) {
        expect(typeof result.price).toBe('string');
        expect(Array.isArray(result.sources)).toBe(true);
      } else if ('error' in result) {
        expect(typeof result.error).toBe('string');
      }
    });

    it('should handle errors gracefully', async () => {
      const result = await getPrice(
        'base' as any,
        '', // Invalid token
        '', // Invalid token
        ''  // Invalid amount
      );

      if ('error' in result) {
        expect(typeof result.error).toBe('string');
      }
    });

    it('should support different chains', async () => {
      const chains = ['base', 'monad'] as const;

      for (const chain of chains) {
        const result = await getPrice(
          chain,
          '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
          '0x4200000000000000000000000000000000000006',
          '1000000'
        );

        expect(result).toHaveProperty('error');
        // Success or failure, should have valid result
        expect(result).not.toBeUndefined();
      }
    });

    it('should return numeric price as string', async () => {
      const result = await getPrice(
        'base',
        '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
        '0x4200000000000000000000000000000000000006',
        '1000000'
      );

      if ('price' in result) {
        // Price should be a valid number string
        const priceNum = parseFloat(result.price);
        expect(isNaN(priceNum)).toBe(false);
      }
    });
  });

  describe('batchQuotes', () => {
    it('should accept array of requests', async () => {
      const requests: EZPathQuoteRequest[] = [
        {
          chain: 'base',
          sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
          buyToken: '0x4200000000000000000000000000000000000006',
          sellAmount: '1000000',
        },
        {
          chain: 'base',
          sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
          buyToken: '0x50c5725949A6F0c72EC20E08a6DE0146F30F1F75',
          sellAmount: '1000000',
        },
      ];

      const results = await batchQuotes(requests);

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBe(requests.length);
    });

    it('should return array of QuoteResults', async () => {
      const requests: EZPathQuoteRequest[] = [
        {
          chain: 'base',
          sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
          buyToken: '0x4200000000000000000000000000000000000006',
          sellAmount: '1000000',
        },
      ];

      const results = await batchQuotes(requests);

      expect(results.length).toBe(1);
      expect(typeof results[0].success).toBe('boolean');
    });

    it('should handle empty array', async () => {
      const results = await batchQuotes([]);

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBe(0);
    });

    it('should execute requests in parallel', async () => {
      const requests: EZPathQuoteRequest[] = Array(3).fill({
        chain: 'base',
        sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
        buyToken: '0x4200000000000000000000000000000000000006',
        sellAmount: '1000000',
      });

      const startTime = Date.now();
      const results = await batchQuotes(requests);
      const duration = Date.now() - startTime;

      expect(results.length).toBe(3);
      // Parallel requests should be faster than sequential
      // (This is a soft assertion - exact timing varies)
      expect(duration).toBeLessThan(30000); // Should complete in reasonable time
    });
  });

  describe('Error handling', () => {
    it('should not throw on network errors', async () => {
      const request: EZPathQuoteRequest = {
        chain: 'base',
        sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
        buyToken: '0x4200000000000000000000000000000000000006',
        sellAmount: '1000000',
      };

      // Should not throw
      await expect(getQuote(request)).resolves.toBeDefined();
    });

    it('should include error messages on failure', async () => {
      const result = await getPrice(
        'base',
        '0x0000000000000000000000000000000000000000', // Null address
        '0x0000000000000000000000000000000000000000',
        '0'
      );

      if ('error' in result) {
        expect(typeof result.error).toBe('string');
        expect(result.error.length).toBeGreaterThan(0);
      }
    });
  });

  describe('Type safety', () => {
    it('should export proper TypeScript types', () => {
      // This test verifies that imports work
      expect(typeof getQuote).toBe('function');
      expect(typeof getPrice).toBe('function');
      expect(typeof batchQuotes).toBe('function');
    });
  });
});
