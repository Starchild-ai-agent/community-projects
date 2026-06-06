# Agent API Integration Guide

**Quick reference for autonomous agents to integrate MONSKILLS EZ-Path via HTTP.**

---

## 🎯 Quick Start

**API Base URL:**
```
Production:  https://api.monskills-ezpath.dev
Sandbox:     https://sandbox-api.monskills-ezpath.dev
Local:       http://localhost:3000
```

**Endpoints:**
```
POST   /v1/quote              Get single DEX quote
POST   /v1/quote/batch        Get multiple quotes in parallel
GET    /v1/health             Health check + venue status
GET    /v1/chains             Supported blockchains
GET    /v1/venues             Supported DEX venues
```

**Rate Limits:**
- 120 requests/minute (public IP)
- 429 with `Retry-After` header if exceeded

---

## 1️⃣ CURL Example

### Simple Quote

```bash
curl -X POST https://api.monskills-ezpath.dev/v1/quote \
  -H "Content-Type: application/json" \
  -d '{
    "chain": "monad",
    "sellToken": "0x4200000000000000000000000000000000000006",
    "buyToken": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "sellAmount": "1000000000000000000"
  }' \
  -w "\nLatency: %{time_total}s\n"
```

### Response

```json
{
  "quote_id": "q_monad_abc123",
  "chain_id": "monad",
  "sell_token": "0x4200000000000000000000000000000000000006",
  "buy_token": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
  "sell_amount": "1000000000000000000",
  "buy_amount": "2500000",
  "route": {
    "venues": ["0x", "Aerodrome", "Uniswap V3"],
    "proportions": [0.4, 0.35, 0.25]
  },
  "gas_estimate": "150000",
  "expires_at": 1717680839,
  "latency_ms": 177,
  "timestamp": "2026-06-06T15:02:39Z"
}
```

### Error Handling

```bash
# Retry on 429 (rate limited)
function retry_quote() {
  local max_attempts=3
  local attempt=1
  
  while [ $attempt -le $max_attempts ]; do
    response=$(curl -s -w "\n%{http_code}" -X POST https://api.monskills-ezpath.dev/v1/quote \
      -H "Content-Type: application/json" \
      -d '{
        "chain": "monad",
        "sellToken": "0x4200000000000000000000000000000000000006",
        "buyToken": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "sellAmount": "1000000000000000000"
      }')
    
    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | head -n -1)
    
    if [ "$http_code" = "200" ]; then
      echo "$body"
      return 0
    elif [ "$http_code" = "429" ]; then
      retry_after=$(echo "$body" | jq -r '.retry_after_seconds // 1')
      sleep "$retry_after"
      ((attempt++))
    else
      echo "Error: $body" >&2
      return 1
    fi
  done
  
  echo "Max retries exceeded" >&2
  return 1
}

retry_quote
```

---

## 2️⃣ Python Example

### Single Quote

```python
import requests
import time
from typing import Optional, Dict, Any

class EZPathAgent:
    def __init__(self, base_url: str = "https://api.monskills-ezpath.dev"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def get_quote(
        self,
        chain: str,
        sell_token: str,
        buy_token: str,
        sell_amount: str,
        max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """Get a DEX quote with automatic retry on rate limit."""
        
        url = f"{self.base_url}/v1/quote"
        payload = {
            "chain": chain,
            "sellToken": sell_token,
            "buyToken": buy_token,
            "sellAmount": sell_amount
        }
        
        for attempt in range(max_retries):
            try:
                response = self.session.post(url, json=payload, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Quote received in {data['latency_ms']}ms")
                    return data
                
                elif response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 1))
                    print(f"⏳ Rate limited. Retrying in {retry_after}s...")
                    time.sleep(retry_after)
                    continue
                
                else:
                    error = response.json()
                    print(f"❌ Error {response.status_code}: {error['error']}")
                    print(f"   Message: {error['message']}")
                    return None
            
            except requests.Timeout:
                print(f"⏱️  Request timed out (attempt {attempt+1}/{max_retries})")
                continue
            except Exception as e:
                print(f"❌ Unexpected error: {str(e)}")
                return None
        
        print(f"❌ Failed after {max_retries} attempts")
        return None
    
    def batch_quotes(self, requests_list: list) -> Optional[Dict[str, Any]]:
        """Get multiple quotes in parallel."""
        
        url = f"{self.base_url}/v1/quote/batch"
        payload = {"requests": requests_list}
        
        try:
            response = self.session.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                error = response.json()
                print(f"❌ Batch error: {error['error']}")
                return None
        
        except Exception as e:
            print(f"❌ Batch request failed: {str(e)}")
            return None
    
    def health_check(self) -> bool:
        """Check API and venue status."""
        
        try:
            response = self.session.get(f"{self.base_url}/v1/health", timeout=2)
            if response.status_code == 200:
                health = response.json()
                print(f"✅ API Status: {health['status']}")
                print(f"   Healthy venues: {len(health['venues']['healthy'])}")
                return health['status'] == 'healthy'
            return False
        except Exception as e:
            print(f"❌ Health check failed: {str(e)}")
            return False

# Usage Example
if __name__ == "__main__":
    agent = EZPathAgent()
    
    # Single quote
    quote = agent.get_quote(
        chain="monad",
        sell_token="0x4200000000000000000000000000000000000006",
        buy_token="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        sell_amount="1000000000000000000"
    )
    
    if quote:
        print(f"\n💰 Best price: {quote['buy_amount']}")
        print(f"   Venues: {', '.join(quote['route']['venues'])}")
        print(f"   Expires: {quote['expires_at']}")
    
    # Batch quotes
    batch = agent.batch_quotes([
        {
            "chain": "monad",
            "sellToken": "0x4200000000000000000000000000000000000006",
            "buyToken": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "sellAmount": "1000000000000000000"
        },
        {
            "chain": "base",
            "sellToken": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "buyToken": "0x4200000000000000000000000000000000000006",
            "sellAmount": "1000000"
        }
    ])
    
    if batch:
        print(f"\n📊 Batch results: {len(batch['results'])} quotes")
    
    # Health check
    agent.health_check()
```

---

## 3️⃣ TypeScript Example

### Single Quote with Full Type Safety

```typescript
import axios, { AxiosInstance } from 'axios';

interface QuoteRequest {
  chain: 'base' | 'monad';
  sellToken: string;
  buyToken: string;
  sellAmount: string;
  slippageTolerance?: number;
}

interface QuoteResponse {
  quote_id: string;
  chain_id: string;
  sell_token: string;
  buy_token: string;
  sell_amount: string;
  buy_amount: string;
  route: {
    venues: string[];
    proportions: number[];
  };
  gas_estimate: string;
  expires_at: number;
  latency_ms: number;
  timestamp: string;
}

interface ErrorResponse {
  error:
    | 'UNSUPPORTED_PAIR'
    | 'INSUFFICIENT_LIQUIDITY'
    | 'QUOTE_TIMEOUT'
    | 'RATE_LIMITED'
    | 'UPSTREAM_ERROR';
  message: string;
  details?: Record<string, any>;
  timestamp: string;
}

class EZPathAgent {
  private client: AxiosInstance;

  constructor(baseUrl: string = 'https://api.monskills-ezpath.dev') {
    this.client = axios.create({
      baseURL: baseUrl,
      timeout: 5000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  async getQuote(request: QuoteRequest, maxRetries: number = 3): Promise<QuoteResponse | null> {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        console.log(`📍 Fetching quote (attempt ${attempt}/${maxRetries})...`);

        const response = await this.client.post<QuoteResponse>('/v1/quote', request);

        console.log(`✅ Quote received in ${response.data.latency_ms}ms`);
        return response.data;
      } catch (error: any) {
        if (error.response?.status === 429) {
          const retryAfter = parseInt(error.response.headers['retry-after'] || '1', 10);
          console.log(`⏳ Rate limited. Retrying in ${retryAfter}s...`);
          await new Promise((resolve) => setTimeout(resolve, retryAfter * 1000));
          continue;
        }

        if (error.response?.status === 408 || error.code === 'ECONNABORTED') {
          console.log(`⏱️  Request timeout (attempt ${attempt}/${maxRetries})`);
          continue;
        }

        const errorData = error.response?.data as ErrorResponse | undefined;
        if (errorData) {
          console.error(`❌ Error ${error.response.status}: ${errorData.error}`);
          console.error(`   Message: ${errorData.message}`);

          // Branch logic based on error type
          switch (errorData.error) {
            case 'UNSUPPORTED_PAIR':
              console.log('   → Try a different token pair');
              return null;
            case 'INSUFFICIENT_LIQUIDITY':
              console.log('   → Reduce sell amount or try different chain');
              return null;
            case 'QUOTE_TIMEOUT':
              console.log('   → Retrying...');
              continue;
            case 'RATE_LIMITED':
              console.log('   → Respecting rate limit');
              continue;
            case 'UPSTREAM_ERROR':
              console.log('   → Upstream service error, retrying...');
              continue;
          }
        }

        console.error(`❌ Unexpected error: ${error.message}`);
        return null;
      }
    }

    console.error(`❌ Failed after ${maxRetries} attempts`);
    return null;
  }

  async batchQuotes(requests: QuoteRequest[]): Promise<QuoteResponse[] | null> {
    try {
      console.log(`📊 Fetching ${requests.length} quotes in parallel...`);

      const response = await this.client.post<{
        batch_id: string;
        results: QuoteResponse[];
        latency_ms: number;
      }>('/v1/quote/batch', { requests });

      console.log(`✅ Batch complete in ${response.data.latency_ms}ms`);
      return response.data.results;
    } catch (error: any) {
      const errorData = error.response?.data as ErrorResponse | undefined;
      console.error(`❌ Batch error: ${errorData?.error || error.message}`);
      return null;
    }
  }

  async isHealthy(): Promise<boolean> {
    try {
      const response = await this.client.get<{
        status: 'healthy' | 'degraded' | 'down';
        venues: {
          healthy: string[];
          degraded: string[];
        };
      }>('/v1/health');

      console.log(`✅ API Status: ${response.data.status}`);
      console.log(`   Healthy venues: ${response.data.venues.healthy.length}`);
      return response.data.status === 'healthy';
    } catch (error) {
      console.error('❌ Health check failed');
      return false;
    }
  }
}

// Usage Example
async function main() {
  const agent = new EZPathAgent();

  // Check health first
  const isHealthy = await agent.isHealthy();
  if (!isHealthy) {
    console.log('⚠️  API degraded, but continuing...');
  }

  // Single quote
  const quote = await agent.getQuote({
    chain: 'monad',
    sellToken: '0x4200000000000000000000000000000000000006',
    buyToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
    sellAmount: '1000000000000000000',
  });

  if (quote) {
    console.log(`\n💰 Best price: ${quote.buy_amount}`);
    console.log(`   Venues: ${quote.route.venues.join(', ')}`);
    console.log(`   Expires at: ${new Date(quote.expires_at * 1000).toISOString()}`);
  }

  // Batch quotes
  const batch = await agent.batchQuotes([
    {
      chain: 'monad',
      sellToken: '0x4200000000000000000000000000000000000006',
      buyToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
      sellAmount: '1000000000000000000',
    },
    {
      chain: 'base',
      sellToken: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
      buyToken: '0x4200000000000000000000000000000000000006',
      sellAmount: '1000000',
    },
  ]);

  if (batch) {
    console.log(`\n📊 Batch results: ${batch.length} quotes`);
    batch.forEach((q, i) => {
      console.log(`   Quote ${i + 1}: ${q.buy_amount}`);
    });
  }
}

main().catch(console.error);
```

---

## 📊 Performance Expectations

### Latency SLA

| Percentile | Latency | Target |
|-----------|---------|--------|
| P50 | 150ms | <200ms |
| P95 | 450ms | <600ms |
| P99 | 1500ms | <2000ms |

### Response Time Breakdown

```
Network latency:     ~20-50ms
Quote computation:   ~100-150ms
Venue aggregation:   ~30-100ms
Response serialization: ~5-20ms
────────────────────────────
Total:              150-320ms (typical)
```

---

## 🚨 Error Handling

### Error Codes (Machine-Friendly)

```
UNSUPPORTED_PAIR         → Token pair not supported
INSUFFICIENT_LIQUIDITY   → No liquidity on any venue
QUOTE_TIMEOUT           → Venues didn't respond in time
RATE_LIMITED            → Too many requests
UPSTREAM_ERROR          → Venue API or blockchain issue
```

### Retry Strategy

```
429 (Rate Limited)
  └─ Read Retry-After header
  └─ Wait that many seconds
  └─ Retry up to 3 times

408 / QUOTE_TIMEOUT
  └─ Exponential backoff: 1s, 2s, 4s
  └─ Max 3 retries

5xx (UPSTREAM_ERROR)
  └─ Exponential backoff: 1s, 2s, 4s
  └─ Max 2 retries (upstream may be slow)

400 (UNSUPPORTED_PAIR / INSUFFICIENT_LIQUIDITY)
  └─ Do NOT retry
  └─ Handle gracefully in agent logic
```

---

## 🔒 Headers & Auth

**No authentication required.** Rate limiting is by IP address.

```
Content-Type: application/json
User-Agent: MyAgent/1.0
X-Request-ID: (optional, for tracking)
```

**Response Headers:**

```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 119
X-RateLimit-Reset: 1717680959
```

---

## 📝 Request/Response Contracts

### Request Validation

```json
{
  "chain": "monad",              // Required: "base" | "monad"
  "sellToken": "0x42...",        // Required: Valid ERC-20 address
  "buyToken": "0x83...",         // Required: Valid ERC-20 address
  "sellAmount": "1000...",       // Required: Numeric string (wei)
  "slippageTolerance": 0.01      // Optional: 0-1 (default: 0.01)
}
```

### Response Structure

All responses include:

```json
{
  "quote_id": "q_monad_abc123",    // Unique identifier
  "timestamp": "2026-06-06T...",   // ISO 8601
  "latency_ms": 177,                // Execution time
  "expires_at": 1717680839          // Unix timestamp
}
```

---

## 🧪 Testing

### Health Check Before Quoting

```bash
curl https://api.monskills-ezpath.dev/v1/health
```

Expected:

```json
{
  "status": "healthy",
  "venues": {
    "healthy": ["0x", "Aerodrome", "Uniswap V3", ...],
    "degraded": []
  }
}
```

### Get Supported Chains

```bash
curl https://api.monskills-ezpath.dev/v1/chains
```

### Get Venue List

```bash
curl https://api.monskills-ezpath.dev/v1/venues
```

---

## 📞 Support

**Documentation:** https://github.com/infiniteezverse/monskills-ezpath  
**Issues:** https://github.com/infiniteezverse/monskills-ezpath/issues  
**Discord:** https://discord.gg/infiniteezverse  

---

**v0.1.1 | Agent-ready API for autonomous trading**
