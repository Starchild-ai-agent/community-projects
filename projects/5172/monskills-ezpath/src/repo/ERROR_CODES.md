# Error Codes Reference

**Machine-friendly error model for agent logic branching.**

All errors follow this structure:

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable message",
  "details": {
    "field": "value"
  },
  "timestamp": "2026-06-06T15:02:39Z"
}
```

---

## HTTP Status Codes

| Code | Meaning | Retry? | Action |
|------|---------|--------|--------|
| 200 | OK | — | Use response |
| 400 | Bad Request | ❌ No | Fix request |
| 408 | Timeout | ✅ Yes | Retry with backoff |
| 429 | Rate Limited | ✅ Yes | Wait + retry |
| 500 | Server Error | ✅ Yes | Retry with backoff |
| 503 | Service Unavailable | ✅ Yes | Retry with backoff |

---

## Error Codes

### `UNSUPPORTED_PAIR`

**HTTP Status:** 400  
**Retry:** ❌ No  
**Meaning:** Token pair is not supported

```json
{
  "error": "UNSUPPORTED_PAIR",
  "message": "Pair USDT/WBTC is not supported on Monad",
  "details": {
    "sell_token": "0x...",
    "buy_token": "0x...",
    "chain": "monad",
    "supported_chains": ["base"]
  },
  "timestamp": "2026-06-06T15:02:39Z"
}
```

**Agent Action:**
```python
if error.error == "UNSUPPORTED_PAIR":
    # Try different token pair
    # Or switch to supported chain
    pass
```

---

### `INSUFFICIENT_LIQUIDITY`

**HTTP Status:** 400  
**Retry:** ❌ No  
**Meaning:** Not enough liquidity on any venue for this amount

```json
{
  "error": "INSUFFICIENT_LIQUIDITY",
  "message": "No venue has sufficient liquidity for 1000000000000000000 WETH",
  "details": {
    "requested_amount": "1000000000000000000",
    "max_available": "500000000000000000",
    "venues_checked": 10,
    "best_venue": "Uniswap V3"
  },
  "timestamp": "2026-06-06T15:02:39Z"
}
```

**Agent Action:**
```python
if error.error == "INSUFFICIENT_LIQUIDITY":
    # Option 1: Reduce sell_amount
    new_amount = int(details["max_available"] * 0.95)  # 5% safety margin
    
    # Option 2: Split across multiple trades
    # Option 3: Use different token pair
    pass
```

---

### `QUOTE_TIMEOUT`

**HTTP Status:** 408  
**Retry:** ✅ Yes (with backoff)  
**Meaning:** One or more venues didn't respond in time

```json
{
  "error": "QUOTE_TIMEOUT",
  "message": "Venues did not respond within 2s timeout",
  "details": {
    "venues_responding": ["0x", "Aerodrome", "Uniswap V3"],
    "venues_timeout": ["1Inch", "CoW"],
    "timeout_ms": 2000,
    "venues_checked": 10,
    "venues_responded": 8
  },
  "timestamp": "2026-06-06T15:02:39Z"
}
```

**Agent Action:**
```python
if error.error == "QUOTE_TIMEOUT":
    # Exponential backoff: 1s, 2s, 4s, 8s
    wait_time = 2 ** retry_attempt
    await asyncio.sleep(wait_time)
    retry()
```

---

### `RATE_LIMITED`

**HTTP Status:** 429  
**Retry:** ✅ Yes (with Retry-After header)  
**Meaning:** Too many requests from this IP/address

```json
{
  "error": "RATE_LIMITED",
  "message": "Rate limit exceeded. Max 120 requests/minute",
  "details": {
    "limit_per_minute": 120,
    "requests_in_window": 121,
    "reset_at": "2026-06-06T15:04:00Z",
    "retry_after_seconds": 35
  },
  "timestamp": "2026-06-06T15:02:39Z"
}
```

**Response Headers:**
```
HTTP/1.1 429 Too Many Requests
Retry-After: 35
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1717680879
```

**Agent Action:**
```python
if response.status_code == 429:
    retry_after = int(response.headers.get('Retry-After', 60))
    await asyncio.sleep(retry_after)
    retry()
```

---

### `UPSTREAM_ERROR`

**HTTP Status:** 500 or 503  
**Retry:** ✅ Yes (with backoff)  
**Meaning:** Venue or blockchain RPC error

```json
{
  "error": "UPSTREAM_ERROR",
  "message": "Venue 'ParaSwap' returned error",
  "details": {
    "venue": "ParaSwap",
    "upstream_error": "RPC endpoint timeout",
    "venues_responding": ["0x", "Aerodrome", "Uniswap V3"],
    "venues_failed": ["ParaSwap", "1Inch"],
    "degraded_routes_available": true
  },
  "timestamp": "2026-06-06T15:02:39Z"
}
```

**Agent Action:**
```python
if error.error == "UPSTREAM_ERROR":
    if details.get("degraded_routes_available"):
        # Use best-effort route from healthy venues
        use_response()
    else:
        # Retry with backoff
        wait_time = 2 ** retry_attempt
        await asyncio.sleep(wait_time)
        retry()
```

---

### `INVALID_REQUEST`

**HTTP Status:** 400  
**Retry:** ❌ No  
**Meaning:** Request format is invalid

```json
{
  "error": "INVALID_REQUEST",
  "message": "Missing required field: sellAmount",
  "details": {
    "missing_fields": ["sellAmount"],
    "invalid_fields": {
      "chain": "Invalid chain 'ethereum', must be one of: base, monad"
    }
  },
  "timestamp": "2026-06-06T15:02:39Z"
}
```

**Agent Action:**
```python
if error.error == "INVALID_REQUEST":
    # Log for debugging
    log_error(error.details)
    # Fix the request in agent code
    # Do NOT retry
    pass
```

---

## Retry Logic Examples

### Python with Exponential Backoff

```python
import asyncio
import aiohttp

async def get_quote_with_retry(session, request, max_retries=3):
    for attempt in range(max_retries):
        try:
            async with session.post(
                'https://api.monskills-ezpath.dev/v1/quote',
                json=request,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                
                error = await resp.json()
                
                # Non-retryable errors
                if error['error'] in ['UNSUPPORTED_PAIR', 'INSUFFICIENT_LIQUIDITY', 'INVALID_REQUEST']:
                    raise ValueError(f"{error['error']}: {error['message']}")
                
                # Retryable errors
                if resp.status == 429:
                    retry_after = int(resp.headers.get('Retry-After', 60))
                    await asyncio.sleep(retry_after)
                    continue
                
                if error['error'] in ['QUOTE_TIMEOUT', 'UPSTREAM_ERROR']:
                    backoff = 2 ** attempt  # 1s, 2s, 4s, 8s
                    await asyncio.sleep(backoff)
                    continue
                
                # Unknown error
                raise Exception(f"Unhandled error: {error}")
        
        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            raise
    
    raise Exception(f"Failed after {max_retries} attempts")
```

### TypeScript with Circuit Breaker

```typescript
interface CircuitBreakerConfig {
  failureThreshold: number;
  resetTimeout: number;
}

class EZPathCircuitBreaker {
  private failureCount = 0;
  private isOpen = false;
  private lastFailureTime = 0;

  async request(fn: () => Promise<any>, config: CircuitBreakerConfig) {
    // Check if circuit should reset
    if (this.isOpen) {
      const timeSinceLastFailure = Date.now() - this.lastFailureTime;
      if (timeSinceLastFailure > config.resetTimeout) {
        this.isOpen = false;
        this.failureCount = 0;
      } else {
        throw new Error('Circuit breaker is open');
      }
    }

    try {
      const result = await fn();
      this.failureCount = 0;
      return result;
    } catch (error: any) {
      this.lastFailureTime = Date.now();
      this.failureCount++;

      if (this.failureCount >= config.failureThreshold) {
        this.isOpen = true;
      }

      // Non-retryable errors
      if (
        error.response?.data?.error === 'UNSUPPORTED_PAIR' ||
        error.response?.data?.error === 'INSUFFICIENT_LIQUIDITY' ||
        error.response?.data?.error === 'INVALID_REQUEST'
      ) {
        throw error;
      }

      // Retryable errors
      throw error;
    }
  }
}
```

---

## Monitoring & Alerting

**Alert when error rate exceeds:**

- `UNSUPPORTED_PAIR`: 0% (should not happen after config validation)
- `INSUFFICIENT_LIQUIDITY`: 5% (liquidity issue on venues)
- `QUOTE_TIMEOUT`: 10% (venue latency issue)
- `UPSTREAM_ERROR`: 5% (venue or RPC degradation)
- `RATE_LIMITED`: 1% (quota management issue)

**Log all errors with:**

```python
{
    "timestamp": "2026-06-06T15:02:39Z",
    "error_code": "UNSUPPORTED_PAIR",
    "request": {
        "chain": "monad",
        "sell_token": "0x...",
        "buy_token": "0x...",
        "sell_amount": "..."
    },
    "response_time_ms": 45,
    "retry_attempt": 0
}
```

---

## Support

**Have a question about error handling?**

- 📖 Docs: https://github.com/infiniteezverse/monskills-ezpath
- 🐛 Issues: https://github.com/infiniteezverse/monskills-ezpath/issues
- 💬 Discord: https://discord.gg/infiniteezverse

---

**v0.1.1 | Machine-friendly error handling for autonomous agents**
