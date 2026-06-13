# agent-policy

A signing policy engine for AI-driven DeFi bots.

Every action an agent proposes is evaluated against a YAML policy before any
key is touched. Three verdicts:

- **ALLOW** — execute immediately
- **ESCALATE** — push to Telegram with approve/deny buttons, block until answered
- **BLOCK** — raise `PolicyViolation`, nothing is sent to the exchange

## Install

```bash
pip install pyyaml requests
```

## Usage

```python
from policy import PolicyEngine
from notifier import TelegramNotifier
from policy_client import PolicyClient

# your existing Orderly client
from client import OrderlyClient
raw = OrderlyClient(base_url, creds)

# load policy
engine = PolicyEngine.from_yaml("policy_natgas.yaml")

# optional: Telegram approval for ESCALATE decisions
notifier = TelegramNotifier()   # reads POLICY_TG_BOT_TOKEN + POLICY_TG_CHAT_ID from env

# wrap: drop-in replacement
client = PolicyClient(raw, engine, notifier=notifier)

# now use client exactly as before — policy is enforced transparently
client.place_order({"symbol": "PERP_NATGAS_USDC", "side": "BUY",
                    "order_type": "LIMIT", "price": 3.15, "quantity": 640})
```

## Policy YAML schema

```yaml
assets:
  allowed: [NATGAS, BTC, ETH]
  max_notional_per_asset: 65000

actions:
  autonomous:               # ALLOW without asking
    - type: place_order
      condition: "notional <= 65000"
    - type: cancel_order

  escalate:                 # push to Telegram, wait for approval
    - type: place_order
      condition: "notional > 65000"
    - type: close_position

  forbidden:                # hard BLOCK, raises PolicyViolation
    - type: withdraw
    - type: cancel_all
    - type: change_leverage

circuit_breakers:
  daily_loss_limit: 1000    # BLOCK all orders if daily realized < -1000
  drawdown_pct: 5.0         # BLOCK if equity drawdown > 5% from 24h high
  consecutive_loss_trades: 8
  margin_ratio_max: 65      # BLOCK if exchange margin ratio > 65%
```

## Env vars (for Telegram notifier)

```
POLICY_TG_BOT_TOKEN   — BotFather token
POLICY_TG_CHAT_ID     — your Telegram user/chat ID
```

## Testing

```bash
cd tests && python test_policy.py
```

## Files

| File | Purpose |
|---|---|
| `policy.py` | Core engine: verdict logic, circuit breakers, condition eval |
| `notifier.py` | Telegram approval loop (inline buttons, timeout) |
| `policy_client.py` | Drop-in `OrderlyClient` wrapper |
| `policy_natgas.yaml` | Ready-to-use policy for the NATGAS MM bot |
| `tests/test_policy.py` | Unit tests (no API keys, no Telegram) |
